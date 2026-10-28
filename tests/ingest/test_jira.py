"""version-01 M4: Jira (Cloud REST v3, Data Center REST v2) against a fake site, plus the ADF and
wiki markup converters. No network."""

import httpx
import pytest
import yaml
from sdlc_config import ConfigError, load_snapshot
from sdlc_loaders import LoaderContext
from sdlc_loaders.atlassian import atlassian_client
from sdlc_loaders.http import HttpClient
from sdlc_loaders.jira import JiraLoader
from sdlc_loaders.jira_text import adf_to_markdown, wiki_to_markdown

from tests.support.entra import TEST_ENV

SITE = "https://acme.atlassian.net"


def text(value, *marks):
    node = {"type": "text", "text": value}
    if marks:
        node["marks"] = [m if isinstance(m, dict) else {"type": m} for m in marks]
    return node


def para(*nodes):
    return {"type": "paragraph", "content": list(nodes)}


ADF = {
    "type": "doc",
    "version": 1,
    "content": [
        {"type": "heading", "attrs": {"level": 2}, "content": [text("Impact")]},
        para(
            text("Ledger "),
            text("writes", "strong"),
            text(" failed, see "),
            text("dashboard", {"type": "link", "attrs": {"href": "https://grafana/x"}}),
        ),
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [para(text("retry queue"))]},
                {
                    "type": "listItem",
                    "content": [
                        para(text("restart")),
                        {
                            "type": "orderedList",
                            "content": [
                                {"type": "listItem", "content": [para(text("drain"))]},
                            ],
                        },
                    ],
                },
            ],
        },
        {"type": "codeBlock", "attrs": {"language": "sql"}, "content": [text("select 1;")]},
        {"type": "panel", "content": [para(text("Customer facing"))]},
        {"type": "mediaSingle", "content": [{"type": "media", "attrs": {"id": "x"}}]},
        {
            "type": "table",
            "content": [
                {
                    "type": "tableRow",
                    "content": [
                        {"type": "tableHeader", "content": [para(text("Env"))]},
                        {"type": "tableHeader", "content": [para(text("State"))]},
                    ],
                },
                {
                    "type": "tableRow",
                    "content": [
                        {"type": "tableCell", "content": [para(text("prod"))]},
                        {"type": "tableCell", "content": [para(text("down|degraded"))]},
                    ],
                },
            ],
        },
    ],
}


def test_adf_to_markdown():
    md = adf_to_markdown(ADF)
    assert md.startswith(
        "## Impact\n\nLedger **writes** failed, see [dashboard](https://grafana/x)"
    )
    assert "- retry queue\n- restart\n  1. drain" in md
    assert "```sql\nselect 1;\n```" in md
    assert "> Customer facing" in md
    assert "| Env | State |\n| --- | --- |\n| prod | down\\|degraded |" in md
    assert adf_to_markdown(None) == "" and adf_to_markdown("plain") == "plain\n"


def test_wiki_to_markdown():
    md = wiki_to_markdown(
        "h2. Impact\r\n"
        "Ledger *writes* failed, see [dashboard|https://grafana/x] and {{lb-pay}}.\r\n"
        "* retry queue\n** nested\n# first step\n"
        "{code:sql}select 1;{code}\n"
        "{panel:title=Note}Customer facing{panel}\n"
        "||Env||State||\n|prod|down|\n!diagram.png!"
    )
    assert "## Impact" in md
    assert "Ledger **writes** failed, see [dashboard](https://grafana/x) and `lb-pay`." in md
    assert "- retry queue\n  - nested\n1. first step" in md
    assert "```sql\nselect 1;\n```" in md
    assert "> Customer facing" in md
    assert "| Env | State |\n| --- | --- |\n| prod | down |" in md
    assert "diagram.png" not in md


# --- loader against a fake site -----------------------------------------------------------------


class FakeJira:
    def __init__(self, cloud=True):
        self.cloud = cloud
        self.issues = {
            "PAY-1": {
                "updated": "2026-10-01T10:00:00.000+0000",
                "summary": "Ledger writes fail",
                "description": ADF if cloud else "h2. Impact\nLedger *writes* failed",
                "issuetype": {"name": "Incident"},
                "status": {"name": "Resolved"},
                "priority": {"name": "High"},
                "components": [{"name": "ledger"}],
                "labels": ["sev1"],
                "issuelinks": [
                    {"type": {"outward": "is caused by"}, "outwardIssue": {"key": "PAY-7"}}
                ],
                "assignee": {"displayName": "Jane Person"},
                "comment": {
                    "comments": [
                        {
                            "created": "2026-10-02T09:00:00.000+0000",
                            "author": {"displayName": "Jane Person"},
                            "body": para(text("rolled back")) if cloud else "rolled back",
                        }
                    ]
                },
                "security": None,
            },
            "PAY-2": {
                "updated": "2026-10-01T10:00:00.000+0000",
                "summary": "Secret",
                "security": {"name": "Security team only"},
            },
            "PAY-3": {
                "updated": "2026-10-03T10:00:00.000+0000",
                "summary": "Retry queue",
                "security": None,
            },
        }
        self.full_fetches: list[str] = []

    def _issue(self, key, fields):
        data = self.issues[key]
        return {"key": key, "fields": {f: data.get(f) for f in fields if f in data}}

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        jql, fields = params["jql"], params["fields"].split(",")
        expected = "/rest/api/3/search/jql" if self.cloud else "/rest/api/2/search"
        assert request.url.path == expected and request.headers["Authorization"]
        if jql.startswith("key in ("):
            keys = jql[len("key in (") : -1].split(",")
            self.full_fetches += keys
        else:
            assert jql == "project = PAY" and set(fields) == {"updated", "security"}
            keys = sorted(self.issues)
        if self.cloud:
            start = int(params.get("nextPageToken", "0"))
            page = keys[start : start + 2]
            body = {"issues": [self._issue(k, fields) for k in page]}
            if start + 2 < len(keys):
                body["nextPageToken"] = str(start + 2)
            else:
                body["isLast"] = True
        else:
            start = int(params.get("startAt", "0"))
            page = keys[start : start + 2]
            body = {"issues": [self._issue(k, fields) for k in page], "total": len(keys)}
        return httpx.Response(200, json=body)


def jira(fake, fields=(), secret_value="bot@acme.com:api-token"):  # noqa: S107
    from sdlc_secrets import EnvSecretStore, SecretResolver

    ctx = LoaderContext(
        repo_root=None,
        cache_root=None,
        secrets=SecretResolver(EnvSecretStore({"SDLC_SECRET_JIRA_PAY": secret_value}), {}),
        allowed_hosts=("acme.atlassian.net",),
    )

    class Source:
        type = "jira"
        credentials = ("secret", "jira-pay")

    make = atlassian_client(Source, ctx)

    def factory():
        real = make()
        return HttpClient(
            ctx.allowed_hosts,
            auth_headers=real._auth_headers,
            transport=httpx.MockTransport(fake.handler),
            sleep=lambda s: None,
        )

    edition = "cloud" if fake.cloud else "datacenter"
    return JiraLoader(SITE, edition, "project = PAY", tuple(fields), factory)


@pytest.mark.parametrize("cloud", [True, False])
def test_issues_become_markdown_and_secured_issues_are_skipped(cloud):
    fake = FakeJira(cloud=cloud)
    loader = jira(
        fake,
        fields=(
            "summary",
            "description",
            "issuetype",
            "status",
            "priority",
            "components",
            "labels",
            "issuelinks",
            "comment",
        ),
    )
    items = {i.path: i for i in loader.items()}
    assert {p for p, i in items.items() if i.restricted} == {"PAY-2"}
    assert sorted(fake.full_fetches) == ["PAY-1", "PAY-3"]  # PAY-2 never fetched
    pay1 = items["PAY-1"]
    assert pay1.title == "PAY-1: Ledger writes fail" and pay1.url == f"{SITE}/browse/PAY-1"
    assert pay1.media_type == "text/markdown"
    md = pay1.text
    assert md.startswith("# PAY-1: Ledger writes fail\n\nType: Incident · Status: Resolved")
    assert "Components: ledger" in md and "Labels: sev1" in md and "Links: is caused by PAY-7" in md
    assert "## Description" in md and "## Impact" in md and "**writes**" in md
    assert "### Comment 2026-10-02" in md and "rolled back" in md
    assert "Jane Person" not in md  # people fields never rendered
    assert loader.all_ids() == {"PAY-1", "PAY-3"}
    assert loader.details == {"issues": 2, "restricted": 1}


def test_only_updated_issues_are_fetched_again():
    fake = FakeJira()
    first = jira(fake)
    list(first.items())
    fake.full_fetches.clear()
    fake.issues["PAY-1"]["updated"] = "2026-10-05T10:00:00.000+0000"
    del fake.issues["PAY-3"]
    fake.issues["PAY-4"] = {
        "updated": "2026-10-05T11:00:00.000+0000",
        "summary": "New",
        "security": None,
    }
    second = jira(fake)
    assert {i.path for i in second.items(first.cursor) if not i.restricted} == {"PAY-1", "PAY-4"}
    assert sorted(fake.full_fetches) == ["PAY-1", "PAY-4"]
    assert second.all_ids() == {"PAY-1", "PAY-4"}  # PAY-3 deleted by the pipeline


def test_an_issue_that_gains_security_is_removed():
    fake = FakeJira()
    first = jira(fake)
    list(first.items())
    fake.issues["PAY-3"]["security"] = {"name": "Restricted"}  # `updated` may not change
    second = jira(fake)
    items = {i.path: i for i in second.items(first.cursor)}
    assert items["PAY-3"].restricted and "PAY-3" not in second.all_ids()


def test_changed_fields_read_everything_again():
    fake = FakeJira()
    first = jira(fake)
    list(first.items())
    fake.full_fetches.clear()
    list(jira(fake, fields=("summary",)).items(first.cursor))
    assert sorted(fake.full_fetches) == ["PAY-1", "PAY-3"]


# --- config ---------------------------------------------------------------------------------------

GOOD = {
    "type": "jira",
    "edition": "cloud",
    "location": SITE,
    "jql": "project = PAY AND issuetype = Incident",
    "fields": ["summary", "description", "comment"],
    "credentials": {"secret": "jira-pay"},
}


def configure(config_dir, spec):
    platform = config_dir / "platform.yaml"
    doc = yaml.safe_load(platform.read_text())
    doc["knowledge"]["allowed_hosts"] = ["acme.atlassian.net", "jira.example.com"]
    platform.write_text(yaml.safe_dump(doc, sort_keys=False))
    path = config_dir / "sources/payments-incidents.yaml"
    doc = yaml.safe_load(path.read_text())
    for key in ("include", "exclude"):
        doc["spec"].pop(key, None)
    doc["spec"].update(spec)
    doc["spec"] = {k: v for k, v in doc["spec"].items() if v is not None}
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_jira_source_loads(config_dir):
    configure(config_dir, GOOD)
    source = load_snapshot(config_dir, "local", TEST_ENV).sources["payments-incidents"]
    assert source.type == "jira" and source.options["jql"] == GOOD["jql"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"jql": None}, "spec/jql: required"),
        ({"jql": "project = PAY ORDER BY created"}, "no ORDER BY"),
        ({"location": "https://jira.example.com"}, "Jira Cloud is https://<site>.atlassian.net"),
        ({"fields": ["assignee"]}, "spec/fields"),
        ({"space": "PAY"}, "spec/space: not used by jira sources"),
        ({"credentials": None}, "spec/credentials: required"),
    ],
)
def test_bad_jira_sources_fail(config_dir, change, message):
    configure(config_dir, {**GOOD, **change})
    with pytest.raises(ConfigError) as exc:
        load_snapshot(config_dir, "local", TEST_ENV)
    assert message in str(exc.value), exc.value


def test_data_center_location_is_free_form(config_dir):
    configure(
        config_dir, {**GOOD, "edition": "datacenter", "location": "https://jira.example.com/jira"}
    )
    assert load_snapshot(config_dir, "local", TEST_ENV).sources["payments-incidents"].type == "jira"
