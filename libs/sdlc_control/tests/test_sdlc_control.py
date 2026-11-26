import pytest
import yaml
from sdlc_connectors import Change, ConnectorError, OpenPullRequest
from sdlc_control import (
    ControlRepository,
    branch_parts,
    feature_branch,
    front_matter,
    links_path,
    path_of,
    plan_kind,
    with_front_matter,
    without_front_matter,
)

ID = "F-20261126-refunds"


class FakeRepo:
    """Branches of files, the last change per (branch, path), and open pull requests."""

    def __init__(self):
        self.files: dict[tuple[str, str], str] = {}
        self.changes: dict[tuple[str, str], Change] = {}
        self.prs: list[OpenPullRequest] = []
        self.heads = {"main"}

    def branches(self, prefix):
        return sorted(b for b in self.heads if b.startswith(prefix))

    def read_file(self, path, ref=None):
        try:
            return self.files[(ref, path)]
        except KeyError:
            raise ConnectorError("not_found", path) from None

    def last_change(self, path, ref):
        return self.changes.get((ref, path))

    def commit_file(self, path, text, branch, message):
        self.files[(branch, path)] = text
        self.changes[(branch, path)] = Change(commit=f"c{len(self.changes)}")

    def open_pull_requests(self):
        return self.prs

    def merge(self, branch, path, text, by, number=7):
        self.files[(branch, path)] = text
        self.changes[(branch, path)] = Change(commit="m1", pull_request=number, merged_by=by, url=f"https://x/{number}")


@pytest.fixture
def repo():
    r = FakeRepo()
    r.heads.add(feature_branch(ID))
    return r


def test_layout_and_front_matter():
    assert path_of(ID, "design") == f"features/{ID}/design.md" and links_path(ID) == f"features/{ID}/links.yaml"
    assert plan_kind("org/app-source") == "plan-app-source"
    with pytest.raises(ValueError):
        plan_kind("org/../x y")
    text = with_front_matter("# Body\n", {"control_id": ID, "approved_by": "ada"})
    assert front_matter(text)["approved_by"] == "ada" and without_front_matter(text) == "# Body\n"
    assert front_matter("no front matter") == {}


def test_branches_name_their_feature_and_artifact():
    assert branch_parts(f"sdlc/{ID}/design-a1b2c3") == {"control_id": ID, "kind": "design"}
    assert branch_parts(f"sdlc/{ID}/plan-app-source") == {"control_id": ID, "kind": "plan-app-source"}
    assert branch_parts("feature/x") == {} and branch_parts(f"sdlc/{ID}/other") == {}


def test_a_feature_is_approved_by_its_front_matter_on_its_branch(repo):
    control = ControlRepository(repo, by="ada@example.test")
    assert control.home(ID) == feature_branch(ID) and control.on_feature_branch(ID)
    repo.commit_file(path_of(ID, "feature"), with_front_matter("# F", {"approved_by": "ada"}), feature_branch(ID), "")
    assert control.approval(ID, "feature")["approved"] is True
    repo.commit_file(path_of(ID, "feature"), "# F, no approval", feature_branch(ID), "")
    assert control.approval(ID, "feature")["reason"] == "the feature has no recorded approval"


def test_a_plan_is_approved_only_by_a_person_merging_into_the_feature_branch(repo):
    control = ControlRepository(repo, system_accounts=["SDLC-Bot"])
    kind = plan_kind("org/app-source")
    assert control.approval(ID, kind) == {
        "path": path_of(ID, kind),
        "branch": feature_branch(ID),
        "published": False,
        "approved": False,
    }
    repo.merge(feature_branch(ID), path_of(ID, kind), "# Plan", by="sdlc-bot")
    found = control.approval(ID, kind)
    assert found["approved"] is False and "system account" in found["reason"]  # a machine user never approves
    repo.merge(feature_branch(ID), path_of(ID, kind), "# Plan", by="grace")
    assert control.approval(ID, kind)["approved"] is True
    repo.commit_file(path_of(ID, kind), "# pushed directly", feature_branch(ID), "")
    assert "did not come from a merged pull request" in control.approval(ID, kind)["reason"]


def test_features_from_before_dec_0013_live_on_main():
    repo = FakeRepo()
    control = ControlRepository(repo)
    assert control.home(ID) == "main" and not control.on_feature_branch(ID)
    repo.merge("main", path_of(ID, "feature"), "# F", by="grace")
    assert control.approval(ID, "feature")["approved"] is True  # merged into main: the DEC-0012 rule


def test_writes_are_recorded_on_the_feature_branch(repo):
    control = ControlRepository(repo, by="system")
    control.record(ID, {"action": "plan_pull_request", "results": {"url": "https://x/1"}})
    control.record(ID, {"action": "implementation_pull_request", "results": {"url": "https://x/2"}})
    doc = yaml.safe_load(repo.files[(feature_branch(ID), links_path(ID))])
    assert [w["action"] for w in doc["writes"]] == ["plan_pull_request", "implementation_pull_request"]
    assert doc["writes"][0]["by"] == "system" and control.links(ID) == doc


def test_open_pull_requests_carry_their_feature(repo):
    repo.prs = [
        OpenPullRequest(1, "plan", "https://x/1", f"sdlc/{ID}/plan-app", "sdlc-bot"),
        OpenPullRequest(2, "other", "https://x/2", "fix/typo"),
    ]
    found = ControlRepository(repo).open_pull_requests()
    assert found[0]["control_id"] == ID and found[0]["kind"] == "plan-app"
    assert "control_id" not in found[1]
