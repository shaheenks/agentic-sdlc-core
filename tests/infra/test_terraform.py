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
    """NFR-SEC-010: the agent and the jobs have no access to saved documents; the two MCP servers
    (core_mcp, and core_mcp_gcp with native_enabled, CH-0022) do."""
    grants = [
        b for _, _, b in tf.of_type("google_storage_bucket_iam") if "artifact_store" in b["bucket"]
    ]
    assert sorted(g["member"] for g in grants) == [
        '${google_service_account.w["mcp"].member}',
        '${google_service_account.w["mcp-gcp"].member}',
    ]


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


def test_no_group_map_or_graph_secret():
    """CH-0011/CH-0012: membership comes from app roles only; nothing creates, grants or mounts a
    group map or a Graph secret."""
    text = "\n".join(path.read_text(encoding="utf-8") for path in TF_DIR.glob("*.tf"))
    text += "\n".join(path.read_text(encoding="utf-8") for path in TF_DIR.glob("*.tfvars"))
    gone = ("groups-yaml", "groups_yaml_path", "entra-graph-secret", "entra_graph_client_secret")
    for name in gone:
        assert name not in text, name


def test_native_mcp_requires_invoker_iam(tf):
    """CH-0013: sdlc-mcp-native is the same service with invoker IAM on (no public access); the
    main service keeps today's setting. Cloud Run then checks the caller's Google ID token."""
    services = json.dumps(tf.locals["mcp_services"])
    assert "native = {name = local.mcp_native_name" in services.replace('\\"', '"')
    assert "public = false" in services and "public = true" in services
    mcp = tf.resource("google_cloud_run_v2_service", "mcp")
    assert mcp["for_each"] == "${local.mcp_services}"
    assert mcp["invoker_iam_disabled"] == "${each.value.public}"


def test_nothing_grants_public_invoke(tf):
    """No resource makes a service public with allUsers / allAuthenticatedUsers (comments aside)."""
    text = json.dumps([body for _, _, body in tf.resources])
    assert "allUsers" not in text and "allAuthenticatedUsers" not in text


def test_only_the_agent_identity_may_invoke_the_native_mcp(tf):
    """CH-0014: one invoker grant on sdlc-mcp-native, to the user agent's Agent Identity from a
    variable (empty = no grant), never to a broad principal."""
    grants = [
        (n, b)
        for t, n, b in tf.resources
        if t == "google_cloud_run_v2_service_iam_member" and "mcp" in json.dumps(b)
    ]
    assert [n for n, _ in grants] == ["mcp_native_agent", "mcp_native_ui"]  # + the UI, CH-0016
    _, grant = grants[0]
    assert grant["member"] == "${var.agent_runtime_principal}"
    assert unquote(grant["role"]) == "roles/run.invoker"
    assert 'mcp[\\"native\\"]' in json.dumps(grant["name"]) or "native" in grant["name"]


def test_agent_gateway_is_config_driven_and_starts_in_dry_run(tf):
    """CH-0015: the gateway, registry entry, IAP extension and policy exist only with
    native_enabled and agent_gateway_enabled; the IAP check fails open only in DRY_RUN; the
    agent's grant is roles/iap.egressor with a tool condition built from the generated policy."""
    gated = [
        ("google_network_services_agent_gateway", "egress"),
        ("google_agent_registry_service", "mcp_native"),
        ("google_network_services_authz_extension", "iap"),
        ("google_network_security_authz_policy", "gateway"),
    ]
    for rtype, name in gated:
        assert tf.resource(rtype, name)["count"] == "${local.gateway_on ? 1 : 0}", name
    assert "var.native_enabled && var.agent_gateway_enabled" in tf.locals["gateway_on"]
    gateway = tf.resource("google_network_services_agent_gateway", "egress")
    assert unquote(gateway["google_managed"][0]["governed_access_path"]) == "AGENT_TO_ANYWHERE"
    ext = tf.resource("google_network_services_authz_extension", "iap")
    assert ext["fail_open"] == "${!var.agent_gateway_enforce}"
    assert "DRY_RUN" in json.dumps(ext["metadata"])
    assert "iapPolicyVersion" in json.dumps(
        ext["metadata"]
    )  # required by the API (V1: IAM allow bindings)
    grant = tf.resource("google_iap_agent_registry_mcp_server_iam_member", "agent")
    assert unquote(grant["role"]) == "roles/iap.egressor"
    assert grant["member"] == "${var.agent_runtime_principal}"
    assert grant["condition"][0]["expression"] == "${local.gateway_tool_condition}"
    assert "local.gateway_policy.tools" in tf.locals["gateway_tool_condition"]
    registry = tf.resource("google_agent_registry_service", "mcp_native")
    assert "local.gateway_policy.toolspec" in registry["mcp_server_spec"][0]["content"]
    assert 'file("${path.module}/generated/gateway_policy.json")' in tf.locals["gateway_policy"]


def test_agent_egress_destinations_are_registered_and_granted_one_by_one(tf):
    """CH-0018: each of the agent's other destinations (Entra keys, Gemini, sessions) is a
    registered endpoint behind the same gate, with one roles/iap.egressor grant to the agent; no
    wildcard host; the tenant id comes only from a variable."""
    egress = {unquote(k): v for k, v in tf.locals["agent_egress"].items()}
    # CH-0022: the engine re-validates Google ID tokens, so Google's keys replace Entra's
    assert set(egress) == {"google-signing-keys", "vertex-ai-global", "vertex-ai-regional"}
    urls = {name: unquote(dest["url"]) for name, dest in egress.items()}
    for name, url in urls.items():
        assert "*" not in url, name
        assert url.startswith("https://"), name
    assert urls["google-signing-keys"] == "https://www.googleapis.com/oauth2/v3/certs"
    registry = tf.resource("google_agent_registry_service", "agent_egress")
    assert registry["for_each"] == "${local.gateway_on ? local.agent_egress : {}}"
    assert unquote(registry["endpoint_spec"][0]["type"]) == "NO_SPEC"
    grant = tf.resource("google_iap_agent_registry_endpoint_iam_member", "agent_egress")
    assert "google_agent_registry_service.agent_egress" in grant["for_each"]
    assert unquote(grant["role"]) == "roles/iap.egressor"
    assert grant["member"] == "${var.agent_runtime_principal}"
    endpoint_grants = [n for t, n, _ in tf.resources if t.startswith("google_iap_agent_registry_")]
    assert sorted(endpoint_grants) == ["agent", "agent_egress"]


def test_no_tenant_id_is_committed_in_terraform():
    """The tenant id reaches the Entra endpoint only through var.entra_tenant_id."""
    guid = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    for path in [*TF_DIR.glob("*.tf"), *TF_DIR.glob("*.tfvars")]:
        assert not guid.search(path.read_text(encoding="utf-8")), path.name


# --- GCP stack (CH-0022) -----------------------------------------------------------------------


def _service_entries(tf) -> dict[str, str]:
    text = json.dumps(tf.locals["mcp_services"]).replace('\\"', '"')
    return {
        "main": text[text.index("main = {") : text.index("}", text.index("main = {"))],
        "native": text[text.index("native = {") : text.index("}", text.index("native = {"))],
    }


def test_native_mcp_runs_core_mcp_gcp_as_its_own_account(tf):
    """sdlc-mcp-native runs the core-mcp-gcp image as the mcp-gcp service account with the Google
    settings; the main service keeps core_mcp, its account and the Entra settings."""
    entries = _service_entries(tf)
    for key, value in {"workload": "mcp", "image": "mcp", "idp": "entra"}.items():
        assert f'{key} = "{value}"' in entries["main"], key
    for key, value in {"workload": "mcp-gcp", "image": "mcp_gcp", "idp": "google"}.items():
        assert f'{key} = "{value}"' in entries["native"], key
    assert "/core-mcp-gcp:" in tf.locals["images"]["mcp_gcp"]
    mcp = tf.resource("google_cloud_run_v2_service", "mcp")
    template = json.dumps(mcp["template"])
    assert "google_service_account.w[each.value.workload].email" in template
    assert "local.images[each.value.image]" in template
    assert "local.mcp_identity_env[each.value.idp]" in template


def test_each_stack_gets_only_its_own_identity_settings(tf):
    """No ENTRA_* on the GCP stack's server and no Google client IDs on the Entra one; the client
    IDs come from a variable (never committed); the shared env carries neither."""
    identity = {unquote(k): v for k, v in tf.locals["mcp_identity_env"].items()}
    assert identity["entra"] == "${local.entra_env}"
    google = identity["google"]
    assert google == {
        "SDLC_OAUTH_CLIENT_IDS": "${var.google_oauth_client_ids}",
        "SDLC_IDENTITY_PROVIDER": '"google"',  # the loader then needs no ENTRA_*
    }
    shared = json.dumps(tf.locals["mcp_env"])
    assert "entra_env" not in shared and "ENTRA_" not in shared
    assert "OAUTH_CLIENT_IDS" not in shared


def test_the_gcp_stack_account_mirrors_the_mcp_account(tf):
    """mcp-gcp gets what mcp has (DB, Vertex AI, its secrets, bundles, artifacts, user connection
    secrets, traces) and only with native_enabled; the Cloud Identity API is enabled with it."""
    base = {unquote(k): v for k, v in tf.locals["workloads_base"].items()}
    workloads = tf.locals["workloads"]
    assert "var.native_enabled" in workloads and '"mcp-gcp"' in workloads
    for item in base["mcp"]["roles"] + base["mcp"]["secrets"]:
        assert item in workloads, item
    secrets = tf.resource("google_project_iam_member", "mcp_gcp_user_secrets")
    assert secrets["count"] == "${var.native_enabled ? 1 : 0}"
    original = tf.resource("google_project_iam_member", "mcp_user_secrets")
    assert secrets["condition"] == original["condition"] and secrets["role"] == original["role"]
    for name in ("config_store_mcp_gcp", "artifact_store_mcp_gcp"):
        grant = tf.resource("google_storage_bucket_iam_member", name)
        assert "var.native_enabled" in grant["count"], name
        assert grant["member"] == '${google_service_account.w["mcp-gcp"].member}', name
    trace = tf.resource("google_project_iam_member", "trace")
    assert "mcp-gcp" in trace["for_each"]
    apis = tf.resource("google_project_service", "apis")
    assert 'var.native_enabled ? ["cloudidentity.googleapis.com"] : []' in apis["for_each"]


def test_volumes_are_declared_in_the_order_cloud_run_returns():
    """Cloud Run returns config-bundles before cloudsql; declared the other way round, every plan
    swaps the two mounts and volumes back and makes a new revision (seen on dev, CH-0022)."""
    text = (TF_DIR / "run.tf").read_text(encoding="utf-8")
    for kind in ("volume_mounts", "volumes"):
        names = re.findall(
            rf'(?:dynamic "{kind}"|^\s*{kind}) \{{.*?name\s+= "([a-z-]+)"', text, re.M | re.S
        )
        cloudsql = [i for i, n in enumerate(names) if n == "cloudsql"]
        bundles = [i for i, n in enumerate(names) if n == "config-bundles"]
        assert len(bundles) == 3 and len(cloudsql) >= 3, (kind, names)
        for b in bundles:  # each config-bundles block directly precedes a cloudsql block
            assert b + 1 in cloudsql, (kind, names)


# --- the native chat UI (CH-0016) --------------------------------------------------------------


def test_native_ui_is_behind_iap_and_nothing_else(tf):
    """sdlc-ui-native exists only with native_enabled and native_ui_enabled, has IAP on and invoker
    IAM on, and its only invoker is IAP's service agent; people pass IAP through one group."""
    ui = tf.resource("google_cloud_run_v2_service", "ui_native")
    assert ui["count"] == "${local.ui_native_on ? 1 : 0}"
    assert "var.native_enabled && var.native_ui_enabled" in tf.locals["ui_native_on"]
    assert ui["iap_enabled"] is True and ui["invoker_iam_disabled"] is False
    invokers = [
        b
        for t, n, b in tf.resources
        if t == "google_cloud_run_v2_service_iam_member" and "ui_native" in json.dumps(b["name"])
    ]
    assert [unquote(b["member"]) for b in invokers] == [
        "serviceAccount:service-${data.google_project.this.number}@gcp-sa-iap.iam.gserviceaccount.com"
    ]
    access = tf.resource("google_iap_web_cloud_run_service_iam_member", "ui_native_access")
    assert unquote(access["role"]) == "roles/iap.httpsResourceAccessor"
    assert unquote(access["member"]) == "group:${var.iap_access_group}"
    assert 'var.iap_access_group != ""' in access["count"]


def test_native_ui_runs_the_agent_runtime_backend_with_declared_settings(tf):
    """The UI's settings: the engine from the agent's principal, the domains from platform.yaml,
    client IDs from variables (not committed), secrets only as Secret Manager references."""
    env = {unquote(k): v for k, v in tf.locals["ui_native_env"].items()}
    assert unquote(env["SDLC_AGENT_BACKEND"]) == "agent-runtime"
    assert env["SDLC_AGENT_ENGINE"] == "${local.agent_engine}"
    assert "var.agent_runtime_principal" in tf.locals["agent_engine"]
    assert "config/platform.yaml" in tf.locals["google_allowed_domains"]
    assert env["SDLC_OAUTH_CLIENT_IDS"] == "${var.google_oauth_client_ids}"
    assert env["SDLC_GOOGLE_WEB_CLIENT_ID"] == "${var.google_web_client_id}"
    assert "services/${local.ui_native_name}" in env["SDLC_IAP_AUDIENCE"]
    assert not [k for k in env if SECRET_NAME.search(k)]
    secrets = {unquote(k): unquote(v) for k, v in tf.locals["ui_native_secret_env"].items()}
    assert secrets == {
        "SDLC_GOOGLE_WEB_CLIENT_SECRET": "google-web-client-secret",
        "SDLC_SESSION_KEY": "ui-session-key",
    }
    ui = tf.resource("google_cloud_run_v2_service", "ui_native")
    assert "native-entry.mjs" in json.dumps(ui["template"])


def test_native_ui_account_gets_agent_runtime_and_mcp_invoke_only(tf):
    """No database, no Groups API, no artifact bucket: Agent Runtime query and the MCP invoker."""
    workloads = tf.locals["workloads"]
    assert '"ui-native" = {roles = ["roles/aiplatform.user"]' in workloads.replace('\\"', '"')
    grant = tf.resource("google_cloud_run_v2_service_iam_member", "mcp_native_ui")
    assert grant["member"] == '${google_service_account.w["ui-native"].member}'
    assert unquote(grant["role"]) == "roles/run.invoker"
    text = "\n".join(p.read_text(encoding="utf-8") for p in TF_DIR.glob("*.tf"))
    assert 'w["ui-native"].member' in text
    assert text.count('w["ui-native"]') == 2  # its service, and the MCP invoker grant
