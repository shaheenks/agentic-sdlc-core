"""H8.2: git sources (read a commit, not the working tree) and whole-path globs."""

import subprocess
from pathlib import Path

import pytest
from sdlc_ingest.files import GitSourceError, _matches, git_repository, walk_git

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [*GIT, "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "repo"
    (root / "docs/deep/er").mkdir(parents=True)
    (root / "samples/x").mkdir(parents=True)
    (root / "README.md").write_text("# top\n")
    (root / "docs/guide.md").write_text("# guide v1\n")
    (root / "docs/deep/er/notes.md").write_text("# deep\n")
    (root / "samples/x/skip.md").write_text("# sample\n")
    (root / "logo.md").write_bytes(b"\x00\x01binary")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "one")
    return root


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("samples/sources/x/y.md", "samples/**", True),  # PurePath.match got this wrong
        ("a/tests/fixtures/b/c.py", "**/tests/fixtures/**", True),
        ("README.md", "**/*.md", True),  # ** also matches zero directories
        ("docs/deep/er/notes.md", "**/*.md", True),
        ("docs/guide.md", "*.md", False),  # * stays within one directory
        ("infra/gcp/Dockerfile", "**/Dockerfile", True),
        ("docs/guide.mdx", "**/*.md", False),
    ],
)
def test_globs_match_the_whole_path(path, pattern, expected):
    assert _matches(path, (pattern,)) is expected


def test_walk_git_reads_the_commit_not_the_working_tree(repo):
    first = git(repo, "rev-parse", "HEAD")
    (repo / "docs/guide.md").write_text("# guide v2 (uncommitted)\n")
    commit, files = walk_git(repo, "HEAD", ("**/*.md",), ("samples/**",))
    got = {f.path: f.text for f in files}
    assert commit == first
    assert got == {
        "README.md": "# top\n",
        "docs/deep/er/notes.md": "# deep\n",
        "docs/guide.md": "# guide v1\n",
    }  # binary logo.md skipped, samples excluded, working-tree edit ignored


def test_walk_git_at_a_pinned_older_commit(repo):
    first = git(repo, "rev-parse", "HEAD")
    (repo / "docs/new.md").write_text("# new\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "two")
    _, at_first = walk_git(repo, first, ("**/*.md",), ())
    _, at_head = walk_git(repo, "HEAD", ("**/*.md",), ())
    assert "docs/new.md" not in {f.path for f in at_first}
    assert "docs/new.md" in {f.path for f in at_head}


def test_unknown_ref_and_missing_repo_fail_clearly(repo, tmp_path):
    with pytest.raises(GitSourceError, match="rev-parse"):
        walk_git(repo, "no-such-ref", ("**/*.md",), ())
    with pytest.raises(GitSourceError, match="not found"):
        git_repository("missing", tmp_path, tmp_path / "cache", "HEAD")
