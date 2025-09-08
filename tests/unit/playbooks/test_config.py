from pathlib import Path

import pytest

from playbooks.config import (
    PlaybooksSettings,
    load_settings,
    resolve_config_files,
)


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_precedence_profiles_env_cli(tmp_path, monkeypatch):
    # Arrange project
    proj = tmp_path / "repo"
    proj.mkdir()
    monkeypatch.chdir(proj)

    write(
        proj / "playbooks.toml",
        """
project = "playbooks"
timeout_s = 60
[model]
provider = "openai"
name = "gpt-4o-mini"
temperature = 0.20
""",
    )

    write(
        proj / "playbooks.prod.toml",
        """
timeout_s = 30
""",
    )

    # Arrange user ($XDG_CONFIG_HOME/playbooks/playbooks.toml)
    xdg = tmp_path / "xdg"

    # Use an explicit user_config_dir override so test is OS-agnostic
    user_dir = xdg / "playbooks"
    user_cfg = user_dir / "playbooks.toml"

    write(
        user_cfg,
        """
[model]
temperature = 0.40
""",
    )

    # user profile overrides just temperature (timeout remains from project.prod)
    write(
        user_cfg.with_name("playbooks.prod.toml"),
        """
[model]
name = "gpt-4o"
""",
    )

    # Env overrides
    monkeypatch.setenv("PLAYBOOKS_MODEL__PROVIDER", "openai")  # same
    monkeypatch.setenv("PLAYBOOKS_MODEL__TEMPERATURE", "0.7")  # numeric via JSON parse
    # CLI overrides (simulated via `overrides` dict)
    overrides = {"timeout_s": 45}

    # Act
    settings, files = load_settings(
        profile="prod", overrides=overrides, user_config_dir=user_dir, cwd=proj
    )

    # Assert files order (lowest→highest among files)
    assert [p.name for p in files] == [
        "playbooks.toml",  # project base
        "playbooks.prod.toml",  # project profile
        "playbooks.toml",  # user base
        "playbooks.prod.toml",  # user profile
    ]

    # Assert effective settings
    assert isinstance(settings, PlaybooksSettings)
    # timeout: project.prod (30) < user.base (no change) < user.prod (no change) < env (no change) < CLI (45)
    assert settings.timeout_s == 45
    # temperature: project.base (0.2) < user.base (0.4) < user.prod (no change) < env (0.7)
    assert abs(settings.model.temperature - 0.7) < 1e-9
    # name: project.base (gpt-4o-mini) < user.base (no change) < user.prod (gpt-4o)
    assert settings.model.name == "gpt-4o"


def test_explicit_path_wins_over_user_and_project(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    monkeypatch.chdir(repo)
    write(repo / "playbooks.toml", "timeout_s = 10\n")

    xdg = tmp_path / "xdg2"
    write(xdg / "playbooks" / "playbooks.toml", "timeout_s = 20\n")
    user_dir = tmp_path / "xdg2" / "playbooks"
    write(user_dir / "playbooks.toml", "timeout_s = 20\n")

    explicit = tmp_path / "custom.toml"
    write(explicit, "timeout_s = 99\n[model]\nname = 'x'\n")

    settings, files = load_settings(
        explicit_path=str(explicit), user_config_dir=user_dir, cwd=repo
    )
    # explicit is last among files → wins before env/CLI
    assert files[-1] == explicit
    assert settings.timeout_s == 99
    assert settings.model.name == "x"


def test_env_nested_complex_types(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(
        tmp_path / "playbooks.toml",
        """
[model]
temperature = 0.25
""",
    )
    # booleans, nulls, numbers, arrays/objects
    monkeypatch.setenv("PLAYBOOKS_MODEL__TEMPERATURE", "1")
    # unknown key should be rejected because extra='forbid'
    monkeypatch.setenv("PLAYBOOKS_MODEL__unknown_field", "123")

    with pytest.raises(Exception):
        load_settings()

    # remove bad key and confirm parsing works
    monkeypatch.delenv("PLAYBOOKS_MODEL__unknown_field")
    s, _ = load_settings()
    assert s.model.temperature == 1.0


def test_resolve_only_existing_files(tmp_path, monkeypatch):
    # No files exist → empty tuple
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))
    files = resolve_config_files(profile="prod", user_config_dir=tmp_path / "empty")
    assert files == ()
