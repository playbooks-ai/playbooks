# Playbooks Configuration — PRD

## 1) Summary & Decision

Playbooks will adopt a **typed, minimal, library‑friendly configuration system** based on **TOML files + environment variables + optional CLI overrides**.

* **Project defaults:** `./playbooks.toml`
* **User overrides:** `$XDG_CONFIG_HOME/playbooks/playbooks.toml` (resolved cross‑platform via `platformdirs.user_config_dir("playbooks")`)
* **Profiles:** `playbooks.<profile>.toml` adjacent to the base file (project and/or user)
* **Env overrides:** `PLAYBOOKS_` prefix, nested keys via `__` (double underscore)
* **Explicit override:** `--config /abs/path` or `PLAYBOOKS_CONFIG=/abs/path`
* **Typing/validation:** Pydantic v2 models (strict; `extra="forbid"`)

**Precedence (last wins):**
`project base < project profile < user base < user profile < explicit --config < env (PLAYBOOKS_*) < CLI overrides`

---

## 2) Goals & Non‑Goals

**Goals**

* Simple, predictable configuration that **doesn’t impose a framework** on downstream apps embedding Playbooks
* Typed schema + validation for early error detection and IDE/tooling support (JSON Schema export)
* Consistent filename across contexts (`playbooks.toml`)
* Clear layering and debuggability (print effective config; show source files)
* Safe by default (no YAML execution hazards; secrets via env only)

**Non‑Goals**

* Multi‑backend config providers (Vault/Redis/etc.) in v1 (can be added via adapters later)
* YAML/INI/JSON formats (TOML only in v1 to reduce ambiguity)
* Implicit magic discovery outside the defined search paths

---

## 3) User Stories

1. **Library user** wants to embed Playbooks; they set a few env vars in their container and commit a `playbooks.toml` to the repo. No extra deps.
2. **CLI user** wants to try a different model and temperature temporarily: they use `PLAYBOOKS_MODEL__TEMPERATURE=0.7 playbooks run` or pass `--temperature 0.7` that maps to the schema.
3. **Team** wants a production profile: commit `playbooks.prod.toml` (project), and developers keep personal defaults in `$XDG_CONFIG_HOME`.
4. **SRE** needs to see what’s in effect: `playbooks config show --effective --mask-secrets` prints the merged, validated config and the file list in precedence order.

---

## 4) Design

### 4.1 Files & Locations

* **Project (checked‑in):** `./playbooks.toml`
* **User (per developer):** `$XDG_CONFIG_HOME/playbooks/playbooks.toml`

  * Linux (example): `~/.config/playbooks/playbooks.toml`
  * macOS (via `platformdirs`): `~/Library/Application Support/playbooks/playbooks.toml`
  * Windows (via `platformdirs`): `%APPDATA%\playbooks\playbooks.toml`
* **Profiles:** `playbooks.<profile>.toml` next to the selected base file. Example: `playbooks.prod.toml`.
* **Explicit path:** `PLAYBOOKS_CONFIG` env var or `--config` CLI flag points at an additional file **loaded after** user/project files.

**Duplicate protection:** only TOML is supported. If multiple explicit files are provided, last one wins. If both project and user have profile files with conflicting keys, user‑profile wins (by precedence).

### 4.2 Merge Semantics

* **Deep‑merge for tables/maps** (recursively)
* **Replace for scalars and arrays** (later value replaces earlier)

### 4.3 Environment Variables

* Prefix: `PLAYBOOKS_`
* Nested paths with `__`: `PLAYBOOKS_MODEL__TEMPERATURE=0.7 → { model: { temperature: 0.7 } }`
* Value parsing:

  * `true/false/null/none` → bool/None
  * JSON‑like (`{}`, `[]`, numbers, quoted strings) parsed via `json.loads`
  * otherwise kept as string

### 4.4 CLI Overrides

* CLI flags (when present) map to the same schema keys and apply **last**.
* Expose commands:

  * `playbooks config show [--effective] [--profile prod] [--mask-secrets]`
  * `playbooks config where` (shows resolved file list in order)
  * `playbooks config doctor` (validation + common issues)

### 4.5 Typing & Validation

* Pydantic v2 models (strict), e.g.:

```toml
# playbooks.toml (example)
project = "playbooks"
timeout_s = 60

[model]
provider = "openai"
name = "gpt-4o-mini"
temperature = 0.2
```

* Unknown keys cause a validation error (typo detection).
* Export JSON Schema for IDE integration (VS Code settings UI, docs generation).

### 4.6 Secrets

* **Not stored in TOML.**
* Provided via env (ideally from a secret manager injecting env at runtime), e.g., `PLAYBOOKS_OPENAI__API_KEY`.
* `--mask-secrets` redacts values whose keys match `*_KEY`, `*_TOKEN`, `*_SECRET`, etc.

### 4.7 Error Handling & UX

* If both project and user bases are missing and no env/CLI provided → error with guidance and a minimal example TOML.
* If both `PLAYBOOKS_CONFIG` and `--config` are set, the CLI flag wins; warn about redundancy.
* On validation failure, print the merged object location paths and hint probable typos.

### 4.8 Performance

* Single pass file IO (handful of small TOML files)
* Pure‑Python deep merge; negligible runtime cost compared to model execution

---

## 5) Precedence Examples

Given:

* `./playbooks.toml` → `timeout_s=60`, `model.temperature=0.2`
* `./playbooks.prod.toml` → `timeout_s=30`
* `$XDG_CONFIG_HOME/playbooks/playbooks.toml` → `model.temperature=0.4`
* `$XDG_CONFIG_HOME/playbooks/playbooks.prod.toml` → `model.name="gpt-4o"`
* `PLAYBOOKS_MODEL__TEMPERATURE=0.7`
* CLI: `--timeout-s 45`

**Effective result (profile=prod):**

* `timeout_s = 45` (CLI beats user/profile)
* `model.temperature = 0.7` (env beats user/profile)
* `model.name = "gpt-4o"` (user profile beats project profile/base)

---

## 6) Public API (Python)

```python
from config import load_settings

settings, files_used = load_settings(
    profile=os.getenv("PLAYBOOKS_PROFILE"),
    explicit_path=os.getenv("PLAYBOOKS_CONFIG"),
    overrides={"timeout_s": 45},  # CLI‑level overrides
)

print(settings.to_json())
```

---

## 7) Deliverables

* `config.py` implementing:

  * `resolve_config_files(profile, explicit_path)`
  * `load_settings(profile, explicit_path, overrides)` → `(PlaybooksSettings, files_used)`
  * deep merge, env parsing, TOML loader
  * Pydantic models (`PlaybooksSettings`, `ModelCfg`), `extra="forbid"`
* `tests/test_config.py` covering precedence, profiles, env parsing, explicit path
* CLI glue (`playbooks config …`) wired to the above

---

## 8) Test Plan (Pytest)

* **Precedence & profiles:** ensure order `project < project.profile < user < user.profile < explicit < env < CLI`
* **Env parsing:** booleans, nulls, numbers, arrays/objects, and rejection of unknown keys
* **Explicit path:** wins over project and user
* **Missing files:** error with actionable message
* **Masking:** `--mask-secrets` redaction logic

(An initial suite is included; expand as CLI surfaces more flags.)

---

## 9) Migration Plan

1. **Introduce** `playbooks.toml` support (non‑breaking). Continue reading existing `.env` for *local dev only*.
2. **Add warnings** when deprecated `.env` keys shadow typed config; suggest moving to TOML or env.
3. **Docs & examples**: add a sample `playbooks.toml` to templates; update README and VS Code docs.
4. **Flip default** in examples and scaffolding to TOML.
5. **Deprecate** reliance on `.env` in CI/CD pipelines (announce date), keep for local dev convenience indefinitely.

---

## 10) Alternatives Considered

* **Dynaconf as default:** feature‑rich but imposes a global settings pattern and adds framework coupling; overkill for a library default.
* **Hydra/OmegaConf:** great for research/sweeps; heavier and YAML‑centric; could be an optional adapter later.
* **`pyproject.toml`** for runtime: recommended only for *tooling* knobs; runtime/deploy settings belong outside build metadata files.

---

## 11) Security & Privacy

* No secrets in files; env‑only (ideally injected by a secret manager)
* Config printouts mask likely secrets by key pattern
* No code execution from config (TOML via stdlib `tomllib`)

---

## 12) Open Questions

* Should we support **`PLAYBOOKS_CONFIG_DIR`** (directory) to auto‑load multiple files in lexicographic order for advanced use?
* Do we want a **`PLAYBOOKS_PROFILE`** default (e.g., `dev`) when none is provided?
* Should we expose a **JSON Schema** command (`playbooks config schema`)?

---

## 13) References (informative)

* TOML v1.0.0 specification
* Pydantic v2 documentation (models, validation, JSON Schema)
* `platformdirs` documentation (cross‑platform config paths)
* 12‑Factor: configuration via environment variables

---

## 14) Appendix — Minimal Example Files

**`./playbooks.toml`**

```toml
project = "playbooks"
timeout_s = 60

[model]
provider = "openai"
name = "gpt-4o-mini"
temperature = 0.2
```

**`$XDG_CONFIG_HOME/playbooks/playbooks.toml`**

```toml
[model]
temperature = 0.4
```

**`./playbooks.prod.toml`**

```toml
timeout_s = 30
```

Command:

```bash
PLAYBOOKS_MODEL__TEMPERATURE=0.7 playbooks run --profile prod --timeout-s 45
```
