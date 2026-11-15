"""The GCP stack's scripts (CH-0022): the engine is deployed for Google identity from declared
settings, and the manual-check sign-in asks Google for an ID token with PKCE.

Offline: no deploy, no browser, no network.
"""

import sys
import urllib.parse
from argparse import Namespace
from pathlib import Path

import pytest
from sdlc_db.artifacts import normalize_oid

from tests.support.config import GOOGLE_DOMAIN, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import deploy_agent_runtime  # noqa: E402
import google_id_token  # noqa: E402

MCP = "https://sdlc-mcp-native-1.region.run.app/mcp"


def args(idp: str) -> Namespace:
    return Namespace(mcp_url=MCP, model="m", model_location="global", idp=idp)


def test_the_engine_serves_the_google_stack_from_declared_settings():
    env = deploy_agent_runtime.engine_env(args("google"), {"SDLC_OAUTH_CLIENT_IDS": "a,b"})
    assert env["SDLC_IDENTITY_PROVIDER"] == "google"
    assert env["SDLC_OAUTH_CLIENT_IDS"] == "a,b"
    assert env["SDLC_ALLOWED_DOMAINS"] == GOOGLE_DOMAIN  # config/platform.yaml identity.google
    assert not [k for k in env if k.startswith("ENTRA_")]
    assert env["SDLC_MCP_IAM_AUDIENCE"] == MCP.removesuffix("/mcp")


def test_the_google_engine_needs_its_client_ids():
    with pytest.raises(SystemExit, match="SDLC_OAUTH_CLIENT_IDS"):
        deploy_agent_runtime.engine_env(args("google"), {"ENTRA_TENANT_ID": "t"})


def test_entra_stays_available_as_a_rollback():
    environ = {"ENTRA_TENANT_ID": "t", "ENTRA_API_CLIENT_ID": "c", "SDLC_OAUTH_CLIENT_IDS": "x"}
    env = deploy_agent_runtime.engine_env(args("entra"), environ)
    assert env["SDLC_IDENTITY_PROVIDER"] == "entra" and env["ENTRA_TENANT_ID"] == "t"
    assert "SDLC_OAUTH_CLIENT_IDS" not in env and "SDLC_ALLOWED_DOMAINS" not in env


def test_allowed_domains_must_be_declared(tmp_path):
    (tmp_path / "platform.yaml").write_text("identity: {}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="allowed_domains"):
        deploy_agent_runtime.allowed_domains(tmp_path)


def test_sign_in_url_asks_for_an_id_token_with_pkce():
    url = google_id_token.authorization_url("cid", "http://127.0.0.1:5", "st", "ch", "corp.test")
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert url.startswith("https://accounts.google.com/")
    assert query["scope"] == "openid email profile" and query["response_type"] == "code"
    assert query["code_challenge_method"] == "S256" and query["code_challenge"] == "ch"
    assert query["state"] == "st" and query["hd"] == "corp.test"
    assert query["redirect_uri"].startswith("http://127.0.0.1:")


def test_sign_in_needs_the_desktop_client():
    with pytest.raises(SystemExit, match="DESKTOP_CLIENT"):
        google_id_token.id_token(environ={})


@pytest.mark.parametrize("owner", ["1" * 21, "AAAAAAAA-0000-0000-0000-00000000000A"])
def test_db_owner_takes_either_stacks_user_id(owner):
    assert normalize_oid(owner) == owner.lower()


@pytest.mark.parametrize("owner", ["", "x", "1" * 65, "user@example.test"])
def test_db_owner_refuses_other_shapes(owner):
    with pytest.raises(ValueError):
        normalize_oid(owner)


def test_scripts_are_where_the_tests_import_them_from():
    assert Path(deploy_agent_runtime.__file__).parent == REPO_ROOT / "scripts"
