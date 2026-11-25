"""The adapters against faked HTTP APIs: what each edition sends, how answers are read, and that errors carry no
credential or body."""

import base64
import json

import httpx
import pytest
from sdlc_connectors import ConnectorError, Credential, FileChange, Jira, adf_to_text, repository, text_to_adf

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
    put = json.loads(fake.seen[3].content)
    assert put["branch"] == "design/PAY-1" and base64.b64decode(put["content"]) == b"# Design"


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
