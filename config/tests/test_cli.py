from sdlc_config.cli import main


def test_validate_accepts_the_repository_config(capsys):
    assert main(["validate", "--env", "local"]) == 0
    assert "config ok" in capsys.readouterr().out


def test_validate_rejects_broken_yaml(tmp_path):
    (tmp_path / "broken.yaml").write_text("a: [1, 2", encoding="utf-8")
    assert main(["validate", "--env", "local", "--dir", str(tmp_path)]) == 1
