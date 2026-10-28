"""version-01 M2: gcs sources against a fake bucket served through the JSON API shapes (no network,
no Google credentials)."""

from urllib.parse import unquote

import httpx
import pytest
import yaml
from sdlc_config import ConfigError, load_snapshot
from sdlc_connectors.http import HttpClient
from sdlc_loaders import LoaderError
from sdlc_loaders.gcs import API_HOSTS, GcsLoader, parse_location

from tests.support.entra import TEST_ENV

PDF = b"%PDF-1.4\n%fake\n"


class FakeBucket:
    """name -> (generation, bytes). Lists in pages of 2; records downloads."""

    def __init__(self, objects: dict[str, tuple[int, bytes]], name="docs-bkt"):
        self.objects, self.name = objects, name
        self.downloads: list[str] = []
        self.status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.host == "storage.googleapis.com"
        if self.status != 200:
            return httpx.Response(self.status, json={"error": {"message": "denied"}})
        path = request.url.raw_path.decode().split("?")[0]
        base = f"/storage/v1/b/{self.name}/o"
        if path == base:  # list
            prefix = request.url.params.get("prefix", "")
            names = sorted(n for n in self.objects if n.startswith(prefix))
            start = int(request.url.params.get("pageToken", "0"))
            page = names[start : start + 2]
            body = {
                "items": [
                    {
                        "name": n,
                        "generation": str(self.objects[n][0]),
                        "size": str(len(self.objects[n][1])),
                    }
                    for n in page
                ]
            }
            if start + 2 < len(names):
                body["nextPageToken"] = str(start + 2)
            return httpx.Response(200, json=body)
        assert path.startswith(base + "/") and request.url.params["alt"] == "media"
        name = unquote(path[len(base) + 1 :])
        generation, data = self.objects[name]
        assert request.url.params["generation"] == str(generation)
        self.downloads.append(name)
        return httpx.Response(200, content=data)


def loader(bucket, location="gs://docs-bkt/team/", include=("**/*.md", "**/*.pdf"), exclude=()):
    return GcsLoader(
        location,
        include,
        exclude,
        client_factory=lambda: HttpClient(
            API_HOSTS, transport=httpx.MockTransport(bucket.handler), sleep=lambda s: None
        ),
    )


@pytest.mark.parametrize(
    ("location", "parsed"),
    [
        ("gs://bkt", ("bkt", "")),
        ("gs://bkt/", ("bkt", "")),
        ("gs://bkt/a/b", ("bkt", "a/b/")),
        ("gs://bkt/a/b/", ("bkt", "a/b/")),
    ],
)
def test_parse_location(location, parsed):
    assert parse_location(location) == parsed


def test_first_run_reads_selected_objects_under_the_prefix():
    bucket = FakeBucket(
        {
            "team/": (1, b""),  # folder placeholder
            "team/runbook.md": (5, b"# Runbook\nrestart"),
            "team/sub dir/guide.md": (6, b"# Guide"),
            "team/spec.pdf": (7, PDF),
            "team/image.png": (8, b"\x89PNG\x00\x00"),
            "team/notes.txt": (9, b"not selected"),
            "team/big.md": (10, b"x" * 1_000_001),  # over the text limit: never downloaded
            "other/secret.md": (11, b"# outside the prefix"),
        }
    )
    gcs = loader(bucket)
    items = {i.path: i for i in gcs.items()}
    assert set(items) == {"runbook.md", "sub dir/guide.md", "spec.pdf"}
    assert items["spec.pdf"].is_pdf and items["runbook.md"].text == "# Runbook\nrestart"
    assert items["sub dir/guide.md"].url == (
        "https://storage.cloud.google.com/docs-bkt/team/sub%20dir/guide.md"
    )
    assert "team/big.md" not in bucket.downloads and "other/secret.md" not in bucket.downloads
    assert gcs.all_ids() == {"runbook.md", "sub dir/guide.md", "spec.pdf"}
    assert gcs.cursor["generations"] == {
        "runbook.md": "5",
        "sub dir/guide.md": "6",
        "spec.pdf": "7",
    }


def test_unchanged_generations_are_not_downloaded():
    bucket = FakeBucket(
        {"team/a.md": (1, b"# A"), "team/b.md": (1, b"# B"), "team/c.md": (1, b"C")}
    )
    first = loader(bucket)
    list(first.items())
    bucket.downloads.clear()
    bucket.objects["team/a.md"] = (2, b"# A2")  # overwritten
    del bucket.objects["team/c.md"]  # deleted
    bucket.objects["team/d.md"] = (1, b"# D")  # new
    second = loader(bucket)
    assert {i.path: i.text for i in second.items(first.cursor)} == {"a.md": "# A2", "d.md": "# D"}
    assert sorted(bucket.downloads) == ["team/a.md", "team/d.md"]
    assert second.all_ids() == {"a.md", "b.md", "d.md"}  # c.md gone -> deleted by the pipeline


def test_a_different_location_reads_everything():
    bucket = FakeBucket({"team/a.md": (1, b"# A")})
    first = loader(bucket)
    list(first.items())
    moved = dict(first.cursor, location="gs://docs-bkt/elsewhere/")
    assert [i.path for i in loader(bucket).items(moved)] == ["a.md"]


def test_exclude_globs_apply_to_names_relative_to_the_prefix():
    bucket = FakeBucket({"team/a.md": (1, b"# A"), "team/drafts/b.md": (1, b"# B")})
    assert [i.path for i in loader(bucket, exclude=("drafts/**",)).items()] == ["a.md"]


def test_access_denied_is_a_loader_error():
    bucket = FakeBucket({"team/a.md": (1, b"# A")})
    bucket.status = 403
    with pytest.raises(LoaderError, match="returned 403"):
        list(loader(bucket).items())


# --- config -------------------------------------------------------------------------------------


def edit(config_dir, spec):
    path = config_dir / "sources/payments-code.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["spec"].update(spec)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_gcs_source_loads(config_dir):
    edit(config_dir, {"type": "gcs", "location": "gs://payments-docs/runbooks/"})
    source = load_snapshot(config_dir, "local", TEST_ENV).sources["payments-code"]
    assert (source.type, source.location) == ("gcs", "gs://payments-docs/runbooks/")


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"type": "gcs", "location": "samples/x"}, "expected gs://<bucket>/<prefix>/"),
        ({"type": "gcs", "location": "gs://Bad_Bucket/x"}, "expected gs://<bucket>/<prefix>/"),
        ({"location": "gs://payments-docs/x"}, "gs:// locations are for gcs sources"),
        (
            {"type": "gcs", "location": "gs://payments-docs/", "credentials": {"env": "KEY"}},
            "gcs sources take no credentials",
        ),
    ],
)
def test_bad_gcs_sources_fail(config_dir, spec, message):
    edit(config_dir, spec)
    with pytest.raises(ConfigError) as exc:
        load_snapshot(config_dir, "local", TEST_ENV)
    assert message in str(exc.value), exc.value
