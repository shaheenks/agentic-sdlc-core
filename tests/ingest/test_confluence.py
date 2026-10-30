"""version-01 M3: Confluence (Cloud and Data Center) against a fake REST v1 site, and the storage
format -> Markdown converter. No network."""

import base64

import httpx
import pytest
import yaml
from sdlc_config import ConfigError, load_snapshot
from sdlc_connectors.http import HttpClient
from sdlc_connectors.storage_format import storage_to_markdown
from sdlc_loaders import LoaderContext
from sdlc_loaders.atlassian import atlassian_client, auth_header_value
from sdlc_loaders.confluence import ConfluenceLoader, read_restricted
from sdlc_secrets import EnvSecretStore, SecretResolver

from tests.support.entra import TEST_ENV

SITE = "https://acme.atlassian.net/wiki"
PDF = b"%PDF-1.4\n%fake attachment\n"

# --- storage format -------------------------------------------------------------------------------

STORAGE = """
<h1>Payments runbook</h1>
<p>Restart the <strong>ledger</strong> service &amp; check <a href="https://status.example.com">status</a>.</p>
<ac:structured-macro ac:name="info"><ac:parameter ac:name="title">Heads up</ac:parameter>
<ac:rich-text-body><p>Only during the change window.</p></ac:rich-text-body></ac:structured-macro>
<h2>Steps</h2>
<ol><li>Drain traffic<ul><li>check <code>lb-pay</code></li></ul></li><li>Restart</li></ol>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter>
<ac:plain-text-body><![CDATA[kubectl rollout restart deploy/ledger
kubectl get pods]]></ac:plain-text-body></ac:structured-macro>
<table><tbody><tr><th>Env</th><th>Owner</th></tr><tr><td><p>prod</p></td><td>payments|sre</td></tr></tbody></table>
<p>See <ac:link><ri:page ri:content-title="Ledger design" /></ac:link> and
<ac:image><ri:attachment ri:filename="diagram.png" /></ac:image> the diagram.</p>
<ac:task-list><ac:task><ac:task-status>complete</ac:task-status>
<ac:task-body>Notify SRE</ac:task-body></ac:task></ac:task-list>
"""


def test_storage_to_markdown():
    md = storage_to_markdown(STORAGE)
    assert md.startswith("# Payments runbook\n")
    assert "Restart the **ledger** service & check [status](https://status.example.com)." in md
    assert "> Only during the change window." in md and "Heads up" not in md
    assert "## Steps" in md
    assert "1. Drain traffic" in md and "  - check `lb-pay`" in md and "2. Restart" in md
    assert "```bash\nkubectl rollout restart deploy/ledger\nkubectl get pods\n```" in md
    assert "| Env | Owner |\n| --- | --- |\n| prod | payments\\|sre |" in md
    assert "See Ledger design and the diagram." in md and "diagram.png" not in md
    assert "- [x] Notify SRE" in md


def test_storage_to_markdown_handles_empty_and_plain_text():
    assert storage_to_markdown("") == ""
    assert storage_to_markdown("just text") == "just text\n"


# --- auth -----------------------------------------------------------------------------------------


def test_auth_header_value():
    basic = auth_header_value("bot@acme.com:api-token").removeprefix("Basic ")
    assert base64.b64decode(basic) == b"bot@acme.com:api-token"
    assert auth_header_value("pat-token") == "Bearer pat-token"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            {"restrictions": {"read": {"restrictions": {"user": {"results": []}, "group": {}}}}},
            False,
        ),
        (
            {"restrictions": {"read": {"restrictions": {"user": {"results": [{"x": 1}]}}}}},
            True,
        ),
        ({"restrictions": {"read": {"restrictions": {"group": {"size": 1}}}}}, True),
        ({}, None),
    ],
)
def test_read_restricted(content, expected):
    assert read_restricted(content) is expected


# --- loader against a fake site -----------------------------------------------------------------


def restrictions(restricted: bool) -> dict:
    users = [{"accountId": "u1"}] if restricted else []
    return {"read": {"restrictions": {"user": {"results": users}, "group": {"results": []}}}}


class FakeConfluence:
    def __init__(self, base=SITE):
        self.base = base
        self.pages = {
            "10": {"title": "Home", "version": 1, "ancestors": [], "restricted": False},
            "1": {"title": "Runbook", "version": 3, "ancestors": ["10"], "restricted": False},
            "2": {"title": "Secret", "version": 1, "ancestors": ["10"], "restricted": True},
            "3": {
                "title": "Under secret",
                "version": 1,
                "ancestors": ["10", "2"],
                "restricted": False,
            },
            "4": {"title": "No expansion", "version": 2, "ancestors": [], "restricted": None},
        }
        self.attachments = [
            {"id": "100", "page": "1", "title": "spec.pdf", "type": "application/pdf"},
            {"id": "101", "page": "2", "title": "secret.pdf", "type": "application/pdf"},
            {"id": "102", "page": "1", "title": "diagram.png", "type": "image/png"},
        ]
        self.body_requests: list[str] = []
        self.auth: dict[str, str | None] = {}

    def _page(self, pid):
        page = self.pages[pid]
        out = {
            "id": pid,
            "type": "page",
            "title": page["title"],
            "version": {"number": page["version"]},
            "ancestors": [{"id": a, "title": self.pages[a]["title"]} for a in page["ancestors"]],
            "_links": {"webui": f"/spaces/PAY/pages/{pid}"},
        }
        if page["restricted"] is not None:
            out["restrictions"] = restrictions(page["restricted"])
        return out

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.auth[request.url.host] = request.headers.get("Authorization")
        if request.url.host == "api.media.atlassian.com":
            return httpx.Response(200, content=PDF)
        path = request.url.path.removeprefix("/wiki").removeprefix("/confluence")
        params = request.url.params
        if path == "/rest/api/content/search":
            cql = params["cql"]
            assert cql.startswith('space = "PAY"')
            if "type = page" in cql:
                rows = [self._page(pid) for pid in sorted(self.pages)]
            else:
                rows = [
                    {
                        "id": a["id"],
                        "title": a["title"],
                        "version": {"number": 1},
                        "container": {"id": a["page"]},
                        "extensions": {"mediaType": a["type"], "fileSize": len(PDF)},
                        "_links": {"download": f"/download/attachments/{a['page']}/{a['title']}"},
                    }
                    for a in self.attachments
                ]
            start = int(params.get("start", "0"))
            body = {"results": rows[start : start + 2], "_links": {"base": self.base}}
            if start + 2 < len(rows):
                body["_links"]["next"] = (
                    f"/rest/api/content/search?cql={params.get('cql', '')}&start={start + 2}"
                    if "cql" in params
                    else None
                )
            return httpx.Response(200, json=body)
        if path.startswith("/rest/api/content/"):
            pid = path.rsplit("/", 1)[-1]
            if params.get("expand") == "body.storage":
                self.body_requests.append(pid)
                storage = f"<h2>About {self.pages[pid]['title']}</h2><p>text {pid}</p>"
                return httpx.Response(
                    200, json={"id": pid, "body": {"storage": {"value": storage}}}
                )
            restricted = bool(self.pages[pid]["restricted"])
            return httpx.Response(200, json={"id": pid, "restrictions": restrictions(restricted)})
        if path.startswith("/download/attachments/"):
            return httpx.Response(302, headers={"Location": "https://api.media.atlassian.com/f/1"})
        return httpx.Response(404)


def confluence(fake, attachments=("pdf",), cql=None, secret="bot@acme.com:api-token"):  # noqa: S107
    secrets = SecretResolver(EnvSecretStore({"SDLC_SECRET_CONFLUENCE_PAY": secret}), {})
    ctx = LoaderContext(
        repo_root=None,
        cache_root=None,
        secrets=secrets,
        allowed_hosts=("acme.atlassian.net", "api.media.atlassian.com"),
    )

    class Source:
        type = "confluence"
        credentials = ("secret", "confluence-pay")

    make = atlassian_client(Source, ctx)

    def factory():
        client = make()
        return HttpClient(
            ctx.allowed_hosts,
            auth_headers=client._auth_headers,
            on_unauthorized=client._on_unauthorized,
            transport=httpx.MockTransport(fake.handler),
            sleep=lambda s: None,
        )

    return ConfluenceLoader(fake.base, "PAY", cql, attachments, factory)


def test_first_run_skips_restricted_pages_and_their_children():
    fake = FakeConfluence()
    loader = confluence(fake)
    items = {i.path: i for i in loader.items()}
    assert {p for p, i in items.items() if i.restricted} == {"PAY/2", "PAY/3"}
    readable = {p: i for p, i in items.items() if not i.restricted}
    assert set(readable) == {"PAY/1", "PAY/4", "PAY/10", "PAY/1/attachments/100"}
    runbook = readable["PAY/1"]
    assert runbook.media_type == "text/markdown" and runbook.title == "Runbook"
    assert runbook.text.startswith("# Runbook\n\nPath: Home > Runbook\n\n## About Runbook")
    assert runbook.url == f"{SITE}/spaces/PAY/pages/1"
    pdf = readable["PAY/1/attachments/100"]
    assert pdf.is_pdf and pdf.raw == PDF and pdf.url == runbook.url
    assert "2" not in fake.body_requests and "3" not in fake.body_requests  # never fetched
    assert loader.all_ids() == {"PAY/1", "PAY/4", "PAY/10", "PAY/1/attachments/100"}
    assert loader.details == {"pages": 3, "restricted": 2}
    # credentials: Basic to the site, never to the media host the download redirected to
    assert fake.auth["acme.atlassian.net"].startswith("Basic ")
    assert fake.auth["api.media.atlassian.com"] is None


def test_only_changed_pages_are_fetched_and_new_restrictions_remove_pages():
    fake = FakeConfluence()
    first = confluence(fake)
    list(first.items())
    fake.body_requests.clear()
    fake.pages["1"]["version"] = 4  # edited
    fake.pages["4"]["restricted"] = True  # restricted since (its version did not change)
    second = confluence(fake)
    items = {i.path: i for i in second.items(first.cursor)}
    assert fake.body_requests == ["1"]
    assert items["PAY/4"].restricted and not items["PAY/1"].restricted
    assert "PAY/4" not in second.all_ids()  # the pipeline deletes the stored copy


def test_changed_selection_reads_everything_again():
    fake = FakeConfluence()
    first = confluence(fake)
    list(first.items())
    fake.body_requests.clear()
    list(confluence(fake, cql="label = runbook").items(first.cursor))
    assert sorted(fake.body_requests) == ["1", "10", "4"]


def test_data_center_uses_bearer_and_its_context_path():
    fake = FakeConfluence(base="https://acme.atlassian.net/confluence")  # DC context path
    token = "dc-personal-access-token"  # noqa: S105 (test value)
    loader = confluence(fake, attachments=(), secret=token)
    assert {i.path for i in loader.items() if not i.restricted} == {"PAY/1", "PAY/4", "PAY/10"}
    assert fake.auth["acme.atlassian.net"] == f"Bearer {token}"
    assert loader.all_ids() == {"PAY/1", "PAY/4", "PAY/10"}


# --- config ---------------------------------------------------------------------------------------


def edit(config_dir, spec, drop=()):
    platform = config_dir / "platform.yaml"
    doc = yaml.safe_load(platform.read_text())
    doc["knowledge"]["allowed_hosts"] = [
        *doc["knowledge"].get("allowed_hosts", []),
        *["acme.atlassian.net", "wiki.example.com"],
    ]
    platform.write_text(yaml.safe_dump(doc, sort_keys=False))
    path = config_dir / "sources/payments-code.yaml"
    doc = yaml.safe_load(path.read_text())
    for key in drop:
        doc["spec"].pop(key, None)
    doc["spec"].update(spec)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


GOOD = {
    "type": "confluence",
    "edition": "cloud",
    "location": SITE,
    "space": "PAY",
    "cql": "label = runbook",
    "attachments": ["pdf"],
    "credentials": {"secret": "confluence-pay"},
}


def test_confluence_source_loads(config_dir):
    edit(config_dir, GOOD, drop=("include", "exclude"))
    source = load_snapshot(config_dir, "local", TEST_ENV).sources["payments-code"]
    assert dict(source.options) == {
        "attachments": ["pdf"],
        "cql": "label = runbook",
        "edition": "cloud",
        "space": "PAY",
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"space": None}, "spec/space: required"),
        ({"credentials": None}, "spec/credentials: required"),
        ({"include": ["**/*.md"]}, "spec/include: not used by confluence sources"),
        (
            {"location": "https://wiki.example.com"},
            "Confluence Cloud is https://<site>.atlassian.net/wiki",
        ),
        ({"attachments": ["docx"]}, "spec/attachments"),
    ],
)
def test_bad_confluence_sources_fail(config_dir, change, message):
    spec = {**GOOD, **{k: v for k, v in change.items() if v is not None}}
    drop = ["include", "exclude", *[k for k, v in change.items() if v is None]]
    for key in drop:
        if key in change and change[key] is not None:
            drop.remove(key)
    edit(config_dir, {k: v for k, v in spec.items() if k not in drop}, drop=drop)
    with pytest.raises(ConfigError) as exc:
        load_snapshot(config_dir, "local", TEST_ENV)
    assert message in str(exc.value), exc.value


def test_confluence_options_are_refused_on_other_types(config_dir):
    edit(config_dir, {"space": "PAY"})
    with pytest.raises(ConfigError, match="spec/space: not used by local_folder sources"):
        load_snapshot(config_dir, "local", TEST_ENV)


def test_data_center_location_is_free_form(config_dir):
    edit(
        config_dir,
        {**GOOD, "edition": "datacenter", "location": "https://wiki.example.com/confluence"},
        drop=("include", "exclude"),
    )
    assert (
        load_snapshot(config_dir, "local", TEST_ENV).sources["payments-code"].options["edition"]
        == "datacenter"
    )
