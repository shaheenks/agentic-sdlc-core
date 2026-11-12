"""E7: the Entra login host comes from platform.yaml and must be consistent."""

import pytest
from sdlc_config import ConfigError, load_snapshot

from tests.config.test_sources_config import edit_yaml
from tests.support.entra import TEST_ENV


def test_hosts_load(config_dir):
    platform = load_snapshot(config_dir, "local", TEST_ENV).platform
    assert platform.authority_host == "https://login.microsoftonline.com"
    assert platform.issuer.startswith(platform.authority_host + "/")


def test_issuer_must_use_the_authority_host(config_dir):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["identity"].update(authority_host="https://login.microsoftonline.us"),
    )
    with pytest.raises(ConfigError, match="identity/issuer must use identity/authority_host"):
        load_snapshot(config_dir, "local", TEST_ENV)


@pytest.mark.parametrize("host", ["http://login.example", "https://login.example/path"])
def test_hosts_are_bare_https_origins(config_dir, host):
    edit_yaml(config_dir / "platform.yaml", lambda d: d["identity"].update(authority_host=host))
    with pytest.raises(ConfigError, match="authority_host"):
        load_snapshot(config_dir, "local", TEST_ENV)
