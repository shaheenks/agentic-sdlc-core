"""infra/gcp keeps its trace claims (CH-0006). CI still runs `terraform validate`.

Offline: parses the .tf files with python-hcl2 (no terraform binary, no GCP access).
"""

import json
import re
from pathlib import Path

import hcl2
import pytest

TF_DIR = Path(__file__).resolve().parents[2] / "infra" / "gcp"

SECRET_NAME = re.compile(r"(PASSWORD|SECRET|_KEY)$")
SECRET_REF = re.compile(r"var\.\w*secret\w*|random_password\.|secret_data")
ENV_KEY = re.compile(r"\b([A-Z][A-Z0-9_]+)\s*=")
LOCAL_ENV_REF = re.compile(r"local\.(\w+_env)\b")


def unquote(value):
    return value[1:-1] if isinstance(value, str) and value[:1] == value[-1:] == '"' else value


class Terraform:
    def __init__(self, directory: Path):
        self.locals: dict = {}
        self.resources: list[tuple[str, str, dict]] = []
        for path in sorted(directory.glob("*.tf")):
            parsed = hcl2.loads(path.read_text(encoding="utf-8"))
            for block in parsed.get("locals", []):
                self.locals.update({k: v for k, v in block.items() if not k.startswith("__")})
            for block in parsed.get("resource", []):
                for rtype, named in block.items():
                    for name, body in named.items():
                        self.resources.append((unquote(rtype), unquote(name), body))

    def of_type(self, prefix: str):
        return [(t, n, b) for t, n, b in self.resources if t.startswith(prefix)]

    def resource(self, rtype: str, name: str) -> dict:
        return next(b for t, n, b in self.resources if (t, n) == (rtype, name))

    def env_text(self, expression: str) -> str:
        """The text of an env map expression with the *_env locals it merges, transitively."""
        seen, todo, parts = set(), [expression], []
        while todo:
            text = todo.pop()
            parts.append(text)
            for ref in LOCAL_ENV_REF.findall(text):
                if ref not in seen:
                    seen.add(ref)
                    todo.append(json.dumps(self.locals[ref]))
        return "\n".join(parts)


@pytest.fixture(scope="module")
def tf() -> Terraform:
    return Terraform(TF_DIR)


def walk_env_blocks(node):
    """Yield (kind, block) for every container env: ('static', env) or ('dynamic', dynamic env)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "env" and isinstance(value, list):
                yield from (("static", b) for b in value)
            elif key == "dynamic" and isinstance(value, list):
                for dyn in value:
                    for label, block in dyn.items():
                        if unquote(label) == "env":
                            yield "dynamic", block
                        else:
                            yield from walk_env_blocks(block)
            else:
                yield from walk_env_blocks(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_env_blocks(item)


def test_only_mcp_has_a_grant_on_the_artifact_bucket(tf):
    """NFR-SEC-010: the agent and the jobs have no access to saved documents."""
    grants = [
        b for _, _, b in tf.of_type("google_storage_bucket_iam") if "artifact_store" in b["bucket"]
    ]
    assert [g["member"] for g in grants] == ['${google_service_account.w["mcp"].member}']


def test_artifact_lifecycle_follows_the_retention_variable(tf):
    """NFR-PRIV-004: saved documents are deleted after the configured retention."""
    bucket = tf.resource("google_storage_bucket", "artifact_store")
    rule = bucket["lifecycle_rule"][0]
    assert rule["condition"][0]["age"] == "${var.artifact_retention_days}"
    assert unquote(rule["action"][0]["type"]) == "Delete"


def test_ingest_and_reconcile_are_scheduled(tf):
    """FR-KNOW-005 (scheduled ingest) and FR-IDN-004 (reconcile revocations)."""
    schedules = json.dumps(tf.locals["schedules"])
    assert "google_cloud_run_v2_job.ingest.name" in schedules
    assert "google_cloud_run_v2_job.reconcile.name" in schedules
    job = tf.resource("google_cloud_scheduler_job", "run")
    assert job["for_each"] == "${local.schedules}"


def test_cloud_run_secrets_are_references_not_plain_values(tf):
    """NFR-SEC-007: secrets reach Cloud Run only as Secret Manager references."""
    runs = tf.of_type("google_cloud_run_v2_")
    assert {(t, n) for t, n, _ in runs} >= {
        ("google_cloud_run_v2_service", "mcp"),
        ("google_cloud_run_v2_service", "app"),
        ("google_cloud_run_v2_job", "ingest"),
    }
    plain_maps = 0
    for _, name, body in runs:
        for kind, block in walk_env_blocks(body):
            if kind == "static":
                if "value" in block:
                    assert not SECRET_NAME.search(unquote(block["name"])), (name, block["name"])
                    assert not SECRET_REF.search(block["value"]), (name, block["name"])
                continue
            content = block["content"][0]
            if "value" not in content:  # value_source.secret_key_ref
                assert "secret_key_ref" in json.dumps(content["value_source"]), name
                continue
            plain_maps += 1
            text = tf.env_text(block["for_each"])
            keys = set(ENV_KEY.findall(text)) | {
                k for ref in LOCAL_ENV_REF.findall(text) for k in tf.locals[ref] if k.isupper()
            }
            assert not [k for k in keys if SECRET_NAME.search(k)], name
            assert not SECRET_REF.search(text), name
    assert plain_maps  # the check saw the env maps
