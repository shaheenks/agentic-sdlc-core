"""The adapters against faked HTTP APIs: what each edition sends, how answers are read, and that errors carry no
credential or body."""

import base64
import json

import httpx
import pytest
from sdlc_connectors import (
    ConnectorError,
    Credential,
    FileChange,
    Jira,
    adf_to_text,
    clone_url,
    repository,
    text_to_adf,
)

TOKEN = "secret-token-never-in-errors"


class Fake:
    """Answers by (method, path); records every request."""

    def __init__(self, routes: dict[tuple[str, str], httpx.Response]):
        self.routes = routes
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        return self.routes.get((request.method, request.url.path), httpx.Response(404, json={"echo": TOKEN}))

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def issue(key, summary="S", status="In Design", kind="Feature", description=None, parent=None):
    fields = {"summary": summary, "status": {"name": status}, "issuetype": {"name": kind}, "description": description}
    if parent:
        fields["parent"] = {"key": parent}
    return {"key": key, "fields": fields}


def test_jira_cloud_signs_in_with_email_and_token_and_reads_adf():
    adf = text_to_adf("Why we need it.\n\nSecond paragraph")
    fake = Fake({("GET", "/rest/api/3/issue/PAY-1"): httpx.Response(200, json=issue("PAY-1", description=adf))})
    jira = Jira("https://x.atlassian.net/", "cloud", Credential(TOKEN, "ada@example.test"), fake.client())
    got = jira.get_issue("PAY-1")
    assert got.description == "Why we need it.\n\nSecond paragraph"
    assert got.url == "https://x.atlassian.net/browse/PAY-1" and got.status == "In Design"
    auth = fake.seen[0].headers["authorization"]
    assert base64.b64decode(auth.removeprefix("Basic ")).decode() == f"ada@example.test:{TOKEN}"


def test_jira_cloud_needs_the_account_email():
    with pytest.raises(ConnectorError):
        Jira("https://x.atlassian.net", "cloud", Credential(TOKEN))


def test_jira_data_center_uses_a_bearer_token_and_v2():
    fake = Fake({("GET", "/rest/api/2/issue/PAY-2"): httpx.Response(200, json=issue("PAY-2", description="plain"))})
    jira = Jira("https://jira.example.test", "data_center", Credential(TOKEN), fake.client())
    assert jira.get_issue("PAY-2").description == "plain"
    assert fake.seen[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_jira_creates_a_story_under_its_feature():
    fake = Fake(
        {
            ("POST", "/rest/api/3/issue"): httpx.Response(201, json={"key": "PAY-3"}),
            ("GET", "/rest/api/3/issue/PAY-3"): httpx.Response(
                200, json=issue("PAY-3", kind="User Story", parent="PAY-1")
            ),
        }
    )
    jira = Jira("https://x.atlassian.net", "cloud", Credential(TOKEN, "a@x.test"), fake.client())
    story = jira.create_issue("PAY", "User Story", "As a payer, I want refunds", "Text", parent="PAY-1")
    sent = json.loads(fake.seen[0].content)["fields"]
    assert sent["project"] == {"key": "PAY"} and sent["parent"] == {"key": "PAY-1"}
    assert sent["description"]["type"] == "doc"
    assert story.parent == "PAY-1"


def test_jira_refuses_a_malformed_key_without_calling():
    fake = Fake({})
    jira = Jira("https://x.atlassian.net", "cloud", Credential(TOKEN, "a@x.test"), fake.client())
    with pytest.raises(ConnectorError):
        jira.get_issue("PAY-1 OR project = OTHER")
    assert fake.seen == []


def test_errors_name_the_status_but_never_the_token_or_body():
    fake = Fake({})
    jira = Jira("https://x.atlassian.net", "cloud", Credential(TOKEN, "a@x.test"), fake.client())
    with pytest.raises(ConnectorError) as raised:
        jira.get_issue("PAY-9")
    assert raised.value.code == "not_found"
    assert TOKEN not in str(raised.value) and TOKEN not in repr(Credential(TOKEN))


def test_adf_lists_and_breaks():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "one"}]}],
                    }
                ],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "a"}, {"type": "hardBreak"}, {"type": "text", "text": "b"}],
            },
        ],
    }
    assert adf_to_text(doc).strip() == "- one\n\na\nb"


def test_github_reads_and_opens_a_pull_request_on_a_new_branch():
    content = base64.b64encode(b"# Readme").decode()
    fake = Fake(
        {
            ("GET", "/repos/o/r/contents/README.md"): httpx.Response(200, json={"type": "file", "content": content}),
            ("GET", "/repos/o/r/git/ref/heads/main"): httpx.Response(200, json={"object": {"sha": "abc"}}),
            ("POST", "/repos/o/r/git/refs"): httpx.Response(201, json={}),
            ("PUT", "/repos/o/r/contents/docs/specs/PAY-1/design.md"): httpx.Response(201, json={}),
            ("POST", "/repos/o/r/pulls"): httpx.Response(
                201, json={"number": 7, "html_url": "https://github.com/o/r/pull/7"}
            ),
        }
    )
    repo = repository("github", "cloud", "https://api.github.com", "o/r", Credential(TOKEN), fake.client())
    assert repo.read_file("README.md") == "# Readme"
    pr = repo.open_pull_request(
        "design/PAY-1",
        "main",
        "PAY-1: design",
        "body",
        [FileChange("docs/specs/PAY-1/design.md", "# Design")],
        "Add design",
    )
    assert (pr.number, pr.url) == (7, "https://github.com/o/r/pull/7")
    assert json.loads(fake.seen[2].content) == {"ref": "refs/heads/design/PAY-1", "sha": "abc"}
    assert fake.seen[3].method == "GET"  # does the file exist on the branch? (404: no)
    put = json.loads(fake.seen[4].content)
    assert put["branch"] == "design/PAY-1" and base64.b64decode(put["content"]) == b"# Design"
    assert "sha" not in put


@pytest.mark.parametrize("bad", ["../etc/passwd", "/abs", "a//b", "a/../b"])
def test_paths_that_leave_the_repository_are_refused(bad):
    repo = repository("github", "cloud", "https://api.github.com", "o/r", Credential(TOKEN), Fake({}).client())
    with pytest.raises(ConnectorError):
        repo.read_file(bad)


def test_bitbucket_cloud_commits_with_a_form_and_opens_a_pull_request():
    fake = Fake(
        {
            ("POST", "/2.0/repositories/w/r/src"): httpx.Response(201),
            ("POST", "/2.0/repositories/w/r/pullrequests"): httpx.Response(
                201, json={"id": 3, "links": {"html": {"href": "https://bitbucket.org/w/r/pull-requests/3"}}}
            ),
        }
    )
    repo = repository("bitbucket", "cloud", "https://api.bitbucket.org", "w/r", Credential(TOKEN), fake.client())
    pr = repo.open_pull_request("design/PAY-1", "main", "t", "b", [FileChange("docs/d.md", "x")], "m")
    assert pr.number == 3
    form = fake.seen[0].content.decode()
    assert "branch=design%2FPAY-1" in form and "docs%2Fd.md=x" in form
    assert "parents=main" in form  # the new branch starts from the base (a feature branch, DEC-0013)
    assert fake.seen[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_bitbucket_data_center_branch_file_and_pull_request():
    base = "/rest/api/1.0/projects/PAY/repos/svc"
    fake = Fake(
        {
            ("POST", f"{base}/branches"): httpx.Response(200, json={}),
            ("PUT", f"{base}/browse/docs/d.md"): httpx.Response(200, json={}),
            ("POST", f"{base}/pull-requests"): httpx.Response(
                201, json={"id": 9, "links": {"self": [{"href": "https://bb/pr/9"}]}}
            ),
        }
    )
    repo = repository(
        "bitbucket", "data_center", "https://bb.example.test", "PAY/svc", Credential(TOKEN), fake.client()
    )
    pr = repo.open_pull_request("design/PAY-1", "main", "t", "b", [FileChange("docs/d.md", "x")], "m")
    assert (pr.number, pr.url) == (9, "https://bb/pr/9")
    assert json.loads(fake.seen[0].content) == {"name": "design/PAY-1", "startPoint": "refs/heads/main"}


# The control repository (DEC-0012): who merged the last change to a file, and a direct commit ---------------------


def test_github_last_change_names_the_merged_pull_request_and_who_merged_it():
    fake = Fake(
        {
            ("GET", "/repos/o/c/commits"): httpx.Response(200, json=[{"sha": "m1"}]),
            ("GET", "/repos/o/c/commits/m1/pulls"): httpx.Response(
                200,
                json=[
                    {"number": 3, "merged_at": None, "base": {"ref": "main"}},
                    {"number": 4, "merged_at": "2026-11-25T10:00:00Z", "base": {"ref": "main"}, "html_url": "u"},
                ],
            ),
            ("GET", "/repos/o/c/pulls/4"): httpx.Response(200, json={"merged_by": {"login": "grace"}}),
        }
    )
    repo = repository("github", "cloud", "https://api.github.com", "o/c", Credential(TOKEN), fake.client())
    change = repo.last_change("features/F-1/feature.md", "main")
    assert (change.commit, change.pull_request, change.merged_by, change.url) == ("m1", 4, "grace", "u")
    assert dict(fake.seen[0].url.params) == {"path": "features/F-1/feature.md", "sha": "main", "per_page": "1"}


def test_github_last_change_of_a_pushed_commit_has_no_pull_request():
    fake = Fake(
        {
            ("GET", "/repos/o/c/commits"): httpx.Response(200, json=[{"sha": "p1"}]),
            ("GET", "/repos/o/c/commits/p1/pulls"): httpx.Response(200, json=[]),
        }
    )
    repo = repository("github", "cloud", "https://api.github.com", "o/c", Credential(TOKEN), fake.client())
    change = repo.last_change("features/F-1/feature.md", "main")
    assert change.commit == "p1" and change.pull_request is None and change.merged_by is None


def test_github_commit_file_replaces_an_existing_file_with_its_sha():
    fake = Fake(
        {
            ("GET", "/repos/o/c/contents/features/F-1/links.yaml"): httpx.Response(200, json={"sha": "old"}),
            ("PUT", "/repos/o/c/contents/features/F-1/links.yaml"): httpx.Response(
                200, json={"commit": {"sha": "new"}}
            ),
        }
    )
    repo = repository("github", "cloud", "https://api.github.com", "o/c", Credential(TOKEN), fake.client())
    assert repo.commit_file("features/F-1/links.yaml", "a: 1\n", "main", "Record links") == "new"
    put = json.loads(fake.seen[1].content)
    assert put["sha"] == "old" and put["branch"] == "main"


def test_bitbucket_cloud_last_change_and_who_closed_it():
    base = "/2.0/repositories/ws/c"
    fake = Fake(
        {
            ("GET", f"{base}/commits/main"): httpx.Response(200, json={"values": [{"hash": "h1"}]}),
            ("GET", f"{base}/commit/h1/pullrequests"): httpx.Response(
                200,
                json={"values": [{"id": 8, "state": "MERGED", "destination": {"branch": {"name": "main"}}}]},
            ),
            ("GET", f"{base}/pullrequests/8"): httpx.Response(200, json={"closed_by": {"nickname": "grace"}}),
        }
    )
    repo = repository("bitbucket", "cloud", "https://api.bitbucket.org", "ws/c", Credential(TOKEN), fake.client())
    change = repo.last_change("features/F-1/feature.md", "main")
    assert (change.commit, change.pull_request, change.merged_by) == ("h1", 8, "grace")


def test_bitbucket_data_center_last_change_reads_the_merge_activity():
    base = "/rest/api/1.0/projects/PAY/repos/c"
    fake = Fake(
        {
            ("GET", f"{base}/commits"): httpx.Response(200, json={"values": [{"id": "d1"}]}),
            ("GET", f"{base}/commits/d1/pull-requests"): httpx.Response(
                200, json={"values": [{"id": 2, "state": "MERGED", "toRef": {"displayId": "main"}}]}
            ),
            ("GET", f"{base}/pull-requests/2/activities"): httpx.Response(
                200, json={"values": [{"action": "COMMENTED"}, {"action": "MERGED", "user": {"name": "grace"}}]}
            ),
            ("PUT", f"{base}/browse/features/F-1/links.yaml"): httpx.Response(200, json={"id": "d2"}),
        }
    )
    repo = repository("bitbucket", "data_center", "https://bb.example.test", "PAY/c", Credential(TOKEN), fake.client())
    change = repo.last_change("features/F-1/feature.md", "main")
    assert (change.commit, change.pull_request, change.merged_by) == ("d1", 2, "grace")
    assert repo.commit_file("features/F-1/links.yaml", "a: 1\n", "main", "Record links") == "d2"
    assert b'name="sourceCommitId"' in fake.seen[-1].content  # replacing a file names its last commit


def test_a_rejected_request_names_the_fields_but_never_their_values():
    body = {"errorMessages": [], "errors": {"issuetype": "Specify a valid issue type secret-ish", "parent": "x"}}
    fake = Fake({("POST", "/rest/api/3/issue"): httpx.Response(400, json=body)})
    jira = Jira("https://x.atlassian.net", "cloud", Credential(TOKEN, "ada@example.test"), fake.client())
    with pytest.raises(ConnectorError) as err:
        jira.create_issue("PAY", "Feature", "S", "")
    assert err.value.code == "invalid"
    assert (
        "issuetype, parent" in err.value.message
        and "secret-ish" not in err.value.message
        and TOKEN not in err.value.message
    )


def test_open_pull_requests_in_every_edition():
    gh = Fake(
        {
            ("GET", "/repos/o/c/pulls"): httpx.Response(
                200,
                json=[
                    {
                        "number": 4,
                        "title": "t",
                        "html_url": "u",
                        "head": {"ref": "sdlc/F-1/feature-a"},
                        "user": {"login": "ada"},
                    }
                ],
            )
        }
    )
    got = repository(
        "github", "cloud", "https://api.github.com", "o/c", Credential(TOKEN), gh.client()
    ).open_pull_requests()
    assert [(p.number, p.branch, p.author) for p in got] == [(4, "sdlc/F-1/feature-a", "ada")]
    assert dict(gh.seen[0].url.params)["state"] == "open"
    bbc = Fake(
        {
            ("GET", "/2.0/repositories/ws/c/pullrequests"): httpx.Response(
                200,
                json={
                    "values": [
                        {"id": 2, "title": "t", "links": {"html": {"href": "u"}}, "source": {"branch": {"name": "b"}}}
                    ]
                },
            )
        }
    )
    assert (
        repository("bitbucket", "cloud", "https://api.bitbucket.org", "ws/c", Credential(TOKEN), bbc.client())
        .open_pull_requests()[0]
        .branch
        == "b"
    )
    base = "/rest/api/1.0/projects/P/repos/c"
    dc = Fake(
        {
            ("GET", f"{base}/pull-requests"): httpx.Response(
                200,
                json={
                    "values": [
                        {"id": 3, "title": "t", "links": {"self": [{"href": "u"}]}, "fromRef": {"displayId": "b2"}}
                    ]
                },
            )
        }
    )
    assert (
        repository("bitbucket", "data_center", "https://bb.example.test", "P/c", Credential(TOKEN), dc.client())
        .open_pull_requests()[0]
        .number
        == 3
    )


def test_jira_finds_a_custom_field_by_name_and_sets_it():
    fields = [{"id": "summary", "name": "Summary"}, {"id": "customfield_10016", "name": "Story point estimate"}]
    fake = Fake(
        {
            ("GET", "/rest/api/3/field"): httpx.Response(200, json=fields),
            ("POST", "/rest/api/3/issue"): httpx.Response(201, json={"key": "PAY-3"}),
            ("GET", "/rest/api/3/issue/PAY-3"): httpx.Response(200, json=issue("PAY-3", kind="Story")),
        }
    )
    jira = Jira("https://x.atlassian.net", "cloud", Credential(TOKEN, "ada@example.test"), fake.client())
    field = jira.field_id(("Story Points", "Story point estimate"))
    assert field == "customfield_10016"
    jira.create_issue(
        "PAY", "Story", "S", "", parent="PAY-1", labels=["size-M", "bad label"], extra={field: 3, "summary": "x"}
    )
    sent = json.loads(fake.seen[1].content)["fields"]
    assert sent["customfield_10016"] == 3 and sent["labels"] == ["size-M"] and sent["summary"] == "S"


def test_branches_are_listed_by_prefix_and_created_once():
    refs = [{"ref": "refs/heads/feature/F-1"}]
    gh = Fake(
        {
            ("GET", "/repos/o/c/git/matching-refs/heads/feature/F-2"): httpx.Response(200, json=[]),
            ("GET", "/repos/o/c/git/matching-refs/heads/feature/F-1"): httpx.Response(200, json=refs),
            ("GET", "/repos/o/c/git/ref/heads/main"): httpx.Response(200, json={"object": {"sha": "abc"}}),
            ("POST", "/repos/o/c/git/refs"): httpx.Response(201, json={}),
        }
    )
    repo = repository("github", "cloud", "https://api.github.com", "o/c", Credential(TOKEN), gh.client())
    assert repo.create_branch("feature/F-2", "main") is True
    assert json.loads(gh.seen[-1].content) == {"ref": "refs/heads/feature/F-2", "sha": "abc"}
    assert repo.create_branch("feature/F-1", "main") is False  # exists: nothing created
    base = "/rest/api/1.0/projects/P/repos/c"
    dc = Fake(
        {
            ("GET", f"{base}/branches"): httpx.Response(200, json={"values": []}),
            ("POST", f"{base}/branches"): httpx.Response(200, json={}),
        }
    )
    repo = repository("bitbucket", "data_center", "https://bb.example.test", "P/c", Credential(TOKEN), dc.client())
    assert repo.create_branch("feature/F-3", "main") is True
    assert json.loads(dc.seen[-1].content) == {"name": "feature/F-3", "startPoint": "refs/heads/main"}


def test_pull_requests_from_an_existing_branch_and_comments_in_every_edition():
    gh = Fake(
        {
            ("POST", "/repos/o/r/pulls"): httpx.Response(
                201, json={"number": 9, "html_url": "https://github.com/o/r/pull/9"}
            ),
            ("POST", "/repos/o/r/issues/9/comments"): httpx.Response(201, json={"html_url": "https://github.com/c/1"}),
        }
    )
    repo = repository("github", "cloud", "https://api.github.com", "o/r", Credential(TOKEN), gh.client())
    pr = repo.create_pull_request("sdlc/F-20261126-x/app", "feature/F-20261126-x", "t", "b")
    assert (pr.number, pr.branch) == (9, "sdlc/F-20261126-x/app")
    assert json.loads(gh.seen[0].content)["base"] == "feature/F-20261126-x"
    assert repo.comment(9, "blocked: the plan names a missing file") == "https://github.com/c/1"
    with pytest.raises(ConnectorError):
        repo.create_pull_request("bad branch", "main", "t", "b")

    bb = Fake(
        {
            ("POST", "/2.0/repositories/w/r/pullrequests"): httpx.Response(
                201, json={"id": 4, "links": {"html": {"href": "https://bitbucket.org/w/r/pull-requests/4"}}}
            ),
            ("POST", "/2.0/repositories/w/r/pullrequests/4/comments"): httpx.Response(
                201, json={"links": {"html": {"href": "https://bitbucket.org/c/2"}}}
            ),
        }
    )
    cloud = repository("bitbucket", "cloud", "https://api.bitbucket.org", "w/r", Credential(TOKEN), bb.client())
    assert cloud.create_pull_request("sdlc/x", "feature/x", "t", "b").number == 4
    assert cloud.comment(4, "hi") == "https://bitbucket.org/c/2"
    assert json.loads(bb.seen[1].content) == {"content": {"raw": "hi"}}

    base = "/rest/api/1.0/projects/PAY/repos/svc"
    dc = Fake(
        {
            ("POST", f"{base}/pull-requests"): httpx.Response(
                201, json={"id": 5, "links": {"self": [{"href": "https://bb.example.com/pr/5"}]}}
            ),
            ("POST", f"{base}/pull-requests/5/comments"): httpx.Response(201, json={"id": 77}),
        }
    )
    server = repository("bitbucket", "data_center", "https://bb.example.com", "PAY/svc", Credential(TOKEN), dc.client())
    assert server.create_pull_request("sdlc/x", "feature/x", "t", "b").number == 5
    assert (
        server.comment(5, "hi") == "https://bb.example.com/projects/PAY/repos/svc/pull-requests/5/overview?commentId=77"
    )


def test_clone_urls():
    assert clone_url("github", "cloud", "https://api.github.com", "o/r") == "https://github.com/o/r.git"
    assert (
        clone_url("github", "data_center", "https://ghe.example.com/api/v3", "o/r") == "https://ghe.example.com/o/r.git"
    )
    assert clone_url("bitbucket", "cloud", "https://api.bitbucket.org", "w/r") == "https://bitbucket.org/w/r.git"
    assert clone_url("bitbucket", "data_center", "https://bb.example.com/", "PAY/svc") == (
        "https://bb.example.com/scm/pay/svc.git"
    )
    with pytest.raises(ValueError):
        clone_url("github", "cloud", "https://api.github.com", "o/r/../x")
