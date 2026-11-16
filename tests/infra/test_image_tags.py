"""Image tags from build inputs (CH-0024; NFR-OPS-002).

Each image's tag is a hash of the committed files its Dockerfile copies, so an image is rebuilt
and its service rolled out only when its own inputs changed. Offline: a throwaway git repo for the
hash, python-hcl2 for Terraform, text checks for the PowerShell script.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import hcl2
import pytest

from tests.infra.test_terraform import TF_DIR, Terraform, unquote
from tests.support.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_tag  # noqa: E402

DEPLOY_PS1 = (REPO_ROOT / "scripts" / "gcp_deploy.ps1").read_text(encoding="utf-8")
TAG = re.compile(r"^src-[0-9a-f]{12}$")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.test")
    git(tmp_path, "config", "user.name", "test")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('v1')\n")
    (tmp_path / "other.txt").write_text("not an input\n")
    (tmp_path / ".dockerignore").write_text(".git\n")
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12-slim\n"
        "COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv\n"
        "COPY --chown=app app/ ./app/\n"
    )
    commit(tmp_path)
    return tmp_path


def commit(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "x")


def test_inputs_are_the_copied_sources_the_dockerfile_and_dockerignore(repo):
    assert build_tag.inputs(repo, "Dockerfile") == [".dockerignore", "Dockerfile", "app"]


def test_the_tag_depends_only_on_committed_inputs(repo):
    first = build_tag.build_tag(repo, "Dockerfile")
    assert TAG.match(first)
    assert build_tag.build_tag(repo, "Dockerfile") == first  # stable

    (repo / "other.txt").write_text("changed\n")
    commit(repo)
    assert build_tag.build_tag(repo, "Dockerfile") == first  # not an input

    (repo / "app" / "main.py").write_text("print('v2')\n")
    assert build_tag.build_tag(repo, "Dockerfile") == first  # uncommitted: not seen
    commit(repo)
    second = build_tag.build_tag(repo, "Dockerfile")
    assert second != first

    (repo / "Dockerfile").write_text((repo / "Dockerfile").read_text() + "ENV X=1\n")
    commit(repo)
    assert build_tag.build_tag(repo, "Dockerfile") != second  # the Dockerfile is an input


def test_a_copied_path_missing_from_the_commit_fails(repo):
    (repo / "Dockerfile").write_text("FROM scratch\nCOPY missing ./missing\n")
    commit(repo)
    with pytest.raises(build_tag.BuildTagError, match="missing"):
        build_tag.build_tag(repo, "Dockerfile")


@pytest.mark.parametrize("key", sorted(build_tag.IMAGES))
def test_every_dockerfile_copy_source_exists_in_the_repo(key):
    _, dockerfile = build_tag.IMAGES[key]
    for source in build_tag.inputs(REPO_ROOT, dockerfile):
        assert (REPO_ROOT / source).exists(), f"{dockerfile} copies {source}, which does not exist"


def test_the_repo_images_get_tags(capsys):
    """`build_tag.py` prints each image's name, Dockerfile and tag (what the script reads)."""
    assert build_tag.main(["--root", str(REPO_ROOT)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert list(printed) == list(build_tag.IMAGES)
    for key, (name, dockerfile) in build_tag.IMAGES.items():
        assert printed[key]["name"] == name and printed[key]["dockerfile"] == dockerfile
        assert TAG.match(printed[key]["tag"])


def test_terraform_takes_one_tag_per_image():
    tf = Terraform(TF_DIR)
    images = {k: unquote(v) for k, v in tf.locals["images"].items() if k != "oauth2_proxy"}
    assert set(images) == set(build_tag.IMAGES)
    for key, (name, _) in build_tag.IMAGES.items():
        assert images[key].endswith(f'/{name}:${{var.image_tags["{key}"]}}'), images[key]

    variables = {}
    for path in sorted(TF_DIR.glob("*.tf")):
        for block in hcl2.loads(path.read_text(encoding="utf-8")).get("variable", []):
            variables.update({unquote(k): v for k, v in block.items()})
    assert "image_tag" not in variables
    condition = json.dumps(variables["image_tags"]["validation"])
    for key in build_tag.IMAGES:
        assert f'\\"{key}\\"' in condition  # the validation names exactly these keys


def test_the_native_ui_does_not_pin_a_launch_stage():
    """Cloud Run reports direct IAP as GA; a pinned BETA showed as a change in every plan."""
    ui = Terraform(TF_DIR).resource("google_cloud_run_v2_service", "ui_native")
    assert "launch_stage" not in ui


def test_the_deploy_script_uses_the_build_tags():
    assert "scripts/build_tag.py" in DEPLOY_PS1
    assert "TF_VAR_image_tags" in DEPLOY_PS1
    assert "TF_VAR_image_tag " not in DEPLOY_PS1 and "TF_VAR_image_tag=" not in DEPLOY_PS1
    assert "artifacts', 'docker', 'images', 'describe'" in DEPLOY_PS1  # skip pushed tags
    assert "[switch]$Rebuild" in DEPLOY_PS1
    # the image list lives in build_tag.py only
    for _name, dockerfile in build_tag.IMAGES.values():
        assert dockerfile not in DEPLOY_PS1, f"{dockerfile} is listed in gcp_deploy.ps1 too"
