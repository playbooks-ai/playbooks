"""
Playbooks configuration loader (TOML, env, CLI overrides)

Locations (same filename for consistency):
- Project defaults (checked in):        ./playbooks.toml
- User overrides (per-dev, cross-OS):   $XDG_CONFIG_HOME/playbooks/playbooks.toml
  (resolved via platformdirs; Linux: $HOME/.config/playbooks, macOS: ~/Library/Application Support/playbooks/, Windows: %APPDATA%\\playbooks\\)

Profiles:
- Optional sibling files named playbooks.<profile>.toml next to the base file.

Precedence (last wins):
project base < project profile < user base < user profile < explicit --config/PLAYBOOKS_CONFIG < env < CLI overrides

Notes:
- Secrets should come from env (or a secret manager injecting env). Do not store secrets in TOML files.
- Env overrides use PLAYBOOKS_ prefix and “__” for nesting, e.g., PLAYBOOKS_MODEL__TEMPERATURE=0.7
- Python 3.11+ is assumed (tomllib). For 3.10, install tomli and keep the import fallback below.
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable, Tuple

from platformdirs import PlatformDirs
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ---------- Typed schema ----------


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # catch typos early

    provider: str = "anthropic"
    name: str = "claude-haiku-4-5-20251001"
    temperature: float = Field(0.2, ge=0, le=2.0)
    max_completion_tokens: int = Field(7500, gt=0)


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")  # allow user-defined models

    execution: ModelConfig | None = None
    compilation: ModelConfig | None = None
    default: ModelConfig | None = None  # fallback model from [model] section

    def model_post_init(self, _):
        if self.default is None:
            self.default = ModelConfig()
        if self.execution is None:
            self.execution = self.default
        if self.compilation is None:
            self.compilation = self.default


class LLMCacheConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # catch typos early

    type: str = "disk"  # "disk" or "redis"
    enabled: bool = True
    path: str = ".llm_cache"  # for disk cache


class LangfuseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # catch typos early

    enabled: bool = True


class LitellmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # catch typos early

    verbose: bool = False


class PlaybooksConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # catch typos early

    timeout_s: int = 60
    debug: bool = False
    artifact_result_threshold: int = Field(
        500, gt=0
    )  # Min chars to auto-create artifact
    max_llm_calls: int = Field(100)
    meeting_message_batch_timeout: float = Field(
        2.0, gt=0
    )  # Rolling timeout for batching meeting messages (seconds)
    meeting_message_batch_max_wait: float = Field(
        10.0, gt=0
    )  # Absolute maximum wait time for oldest message in batch (seconds)
    timestamp_granularity: int = Field(
        0, ge=-3, le=6
    )  # Timestamp granularity: 0=seconds, 3=milliseconds, -1=10s, etc.
    model: ModelsConfig = ModelsConfig()
    llm_cache: LLMCacheConfig = LLMCacheConfig()
    langfuse: LangfuseConfig = LangfuseConfig()
    litellm: LitellmConfig = LitellmConfig()

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


# ---------- Paths & discovery ----------

APPNAME = "playbooks"
FILENAME = "playbooks.toml"


def project_cfg_file(cwd: Path | None = None) -> Path:
    root = cwd or Path.cwd()
    return root / FILENAME


def user_cfg_file(user_dir: Path | None = None) -> Path:
    """Return user config file path, allowing an explicit override for tests."""
    if user_dir is not None:
        return Path(user_dir) / FILENAME
    # `appauthor=False` yields ~/.config/playbooks on Linux
    dirs = PlatformDirs(appname=APPNAME, appauthor=False)
    return Path(dirs.user_config_dir) / FILENAME


def profile_variant(base: Path, profile: str | None) -> Path | None:
    if not profile:
        return None
    prof = base.with_name(f"{base.stem}.{profile}{base.suffix}")
    return prof if prof.exists() else None


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        data = tomllib.load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a top-level TOML table (mapping).")
    return data


# ---------- Merge & env handling ----------


def deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two mappings (dicts). Lists and scalars are replaced by b."""
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)  # type: ignore[assignment]
        else:
            out[k] = v
    return out


def _parse_env_value(raw: str) -> Any:
    s = raw.strip()
    # bool/null
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none"):
        return None
    # numbers / objects / arrays via JSON if it looks JSON-ish or numeric
    if (s and s[0] in '{["-0123456789') or s in ("0",):
        try:
            return json.loads(s)
        except Exception:
            pass
    return s


def apply_env_overrides(
    base: dict[str, Any], prefix: str = "PLAYBOOKS_", nested_delim: str = "__"
) -> dict[str, Any]:
    """Overlay environment variables onto base dict using nested paths."""
    result = dict(base)
    # Skip profile and environment control variables - they're for config selection, not config content
    skip_keys = {"profile", "environment"}
    for k, v in os.environ.items():
        if not k.startswith(prefix):
            continue
        path = k[len(prefix) :]
        parts = path.split(nested_delim)
        # normalize to lower-case keys to match typical TOML style
        parts = [p.lower() for p in parts if p]
        # Skip profile selection variables
        if parts and parts[0] in skip_keys:
            continue
        _set_by_path(result, parts, _parse_env_value(v))
    return result


def _set_by_path(obj: dict[str, Any], parts: Iterable[str], value: Any) -> None:
    it = iter(parts)
    cur = obj
    try:
        last = next(it)
    except StopIteration:
        return
    for p in it:
        cur = cur.setdefault(last, {})
        if not isinstance(cur, dict):
            raise TypeError(f"Cannot set nested key under non-dict at {last}")
        last = p
    cur.setdefault(last, None)
    cur[last] = value


# ---------- Public API ----------


def resolve_config_files(
    profile: str | None = None,
    explicit_path: str | os.PathLike[str] | None = None,
    cwd: Path | None = None,
    user_config_dir: Path | None = None,
) -> Tuple[Path, ...]:
    """Return the list of config files to load in order (lowest → highest precedence among files)."""
    files: list[Path] = []
    proj = project_cfg_file(cwd)
    if proj.exists():
        files.append(proj)
        if prof := profile_variant(proj, profile):
            files.append(prof)

    user = user_cfg_file(user_config_dir)
    if user.exists():
        files.append(user)
        if prof := profile_variant(user, profile):
            files.append(prof)

    if explicit_path:
        ep = Path(explicit_path).expanduser()
        if ep.exists():
            files.append(ep)

    return tuple(files)


def load_config(
    *,
    profile: str | None = None,
    explicit_path: str | os.PathLike[str] | None = None,
    overrides: dict[str, Any] | None = None,
    cwd: Path | None = None,
    user_config_dir: Path | None = None,
) -> Tuple[PlaybooksConfig, Tuple[Path, ...]]:
    """
    Load config with precedence:
    files (project<profile<user<profile<explicit>) < env(PLAYBOOKS_*) < CLI overrides (passed in `overrides`)
    Returns (config, files_used)
    """
    # Auto-detect profile from environment if not explicitly provided
    if profile is None:
        profile = os.environ.get("PLAYBOOKS_PROFILE") or os.environ.get("ENVIRONMENT")

    files = resolve_config_files(
        profile=profile,
        explicit_path=explicit_path,
        cwd=cwd,
        user_config_dir=user_config_dir,
    )
    merged: dict[str, Any] = {}
    for f in files:
        merged = deep_merge(merged, _load_toml(f))

    merged = apply_env_overrides(merged, prefix="PLAYBOOKS_", nested_delim="__")

    if overrides:
        merged = deep_merge(merged, overrides)

    # Handle [model] section as default fallback before validation
    if "model" in merged and isinstance(merged["model"], dict):
        model_section = merged["model"]
        if "provider" in model_section:
            # This is a direct [model] section with model config
            # Extract only ModelConfig fields for the default
            default_model = {
                k: v
                for k, v in model_section.items()
                if k in ["provider", "name", "temperature", "max_completion_tokens"]
                and not isinstance(v, dict)
            }
            merged["model"]["default"] = default_model

    try:
        config = PlaybooksConfig.model_validate(merged)
        return config, files
    except ValidationError as e:
        # pretty print and exit if used as a CLI helper
        print(e, file=sys.stderr)
        raise


# Global config instance
config, _ = load_config()


__all__ = [
    "PlaybooksConfig",
    "ModelConfig",
    "ModelsConfig",
    "LLMCacheConfig",
    "LangfuseConfig",
    "config",
    "load_config",
    "resolve_config_files",
    "deep_merge",
    "apply_env_overrides",
]
