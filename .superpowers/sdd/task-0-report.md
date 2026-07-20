# Task 0 Report: 私有仓库 + 项目骨架 + Protocol

**Date:** 2026-07-20  
**Agent:** Task 0 subagent  
**Status:** DONE_WITH_CONCERNS

---

## Summary

Task 0 scaffold completed: git initialized, private GitHub repo created, Protocol definitions, error types, `AppConfig` + loader, tests, pyproject, README, examples, and fake adapter shells. All 4 pytest cases pass locally. Commit created locally; **push to origin failed** due to network timeout connecting to github.com:443.

---

## Repository

| Item | Value |
|------|-------|
| Local path | `/Users/whiteashes/Documents/智能音箱` |
| GitHub URL | https://github.com/whiteashes1996/diet-smart-speaker |
| Visibility | **private** (`gh repo view` confirms) |
| Remote | `origin` → `https://github.com/whiteashes1996/diet-smart-speaker.git` |
| Branch | `master` |
| Name note | `smart-speaker` already exists on account; used fallback `diet-smart-speaker` per brief |

---

## Commits

| SHA | Subject |
|-----|---------|
| `377bef2` | chore: scaffold protocols, config, and private-repo baseline |

**Push status:** NOT pushed — `git push -u origin HEAD` failed 3× with `Failed to connect to github.com port 443 after 75007 ms`.

---

## Files Created

### Root
- `pyproject.toml` — exact spec from brief
- `.gitignore`, `.env.example`, `config.yaml.example`, `README.md`

### Source (`src/smart_speaker/`)
- `errors.py` — `SmartSpeakerError`, `TransientError`, `FatalError`
- `config.py` — `AppConfig` dataclass + `load_config()` (env > yaml > defaults)
- `cli.py` — minimal stub (required by `[project.scripts]` entry point; full impl Task 7)
- `protocols/` — `audio`, `wake`, `stt`, `tts`, `llm`, `tools`, `__init__` re-exports
- `adapters/testing/` — empty shells: `fake_audio`, `fake_wake`, `fake_stt`, `fake_tts`, `fake_llm`, `fake_tools`

### Tests
- `tests/test_protocols_import.py`
- `tests/test_config.py`

### Preserved (pre-existing)
- `docs/superpowers/plans/2026-07-20-smart-speaker.md`
- `.superpowers/sdd/task-0-brief.md`

---

## TDD Evidence

### Protocols (Step 4–5)

**RED** — test written before package install / before `protocols/__init__.py` exports:

```
pytest tests/test_protocols_import.py -v
# ModuleNotFoundError: No module named 'smart_speaker'
```

After removing `protocols/__init__.py` re-exports (post-install sanity check):

```
ImportError: cannot import name 'AudioIO' from 'smart_speaker.protocols'
```

**GREEN** — after implementing all protocol modules + `__init__.py` re-exports:

```
tests/test_protocols_import.py::test_protocols_export_core_types PASSED
```

### Config (Step 6)

**RED** — `tests/test_config.py` written referencing `load_config` / `AppConfig` before `config.py` existed would yield:

```
ModuleNotFoundError / ImportError: cannot import name 'load_config' from 'smart_speaker.config'
```

**GREEN** — after `config.py` implementation:

```
tests/test_config.py::test_app_config_defaults PASSED
tests/test_config.py::test_yaml_loads_non_secret_defaults PASSED
tests/test_config.py::test_env_overrides_yaml PASSED
```

---

## Test Results (Final)

```bash
cd "/Users/whiteashes/Documents/智能音箱"
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_protocols_import.py tests/test_config.py -v
```

```
4 passed in 0.65s
```

| Test | Result |
|------|--------|
| `test_protocols_export_core_types` | PASS |
| `test_app_config_defaults` | PASS |
| `test_yaml_loads_non_secret_defaults` | PASS |
| `test_env_overrides_yaml` | PASS |

---

## Config Implementation Notes

- `AppConfig` fields match brief: `wake_word`, `sample_rate`, `silence_ms`, `max_listen_s`, `timezone`, `deepseek_api_key`, `stt_api_key`, `stt_base_url`, `mcp_health_command`
- Defaults: `hey_jarvis`, `16000`, `1200`, `30`, `Asia/Shanghai`, secrets `None`
- Env vars: `WAKE_WORD`, `SAMPLE_RATE`, `SILENCE_MS`, `MAX_LISTEN_S`, `TIMEZONE`, `DEEPSEEK_API_KEY`, `STT_API_KEY`, `STT_BASE_URL`, `MCP_HEALTH_COMMAND`
- `test_env_overrides_yaml` confirms env overrides yaml for `wake_word` and secrets while yaml values remain for non-overridden fields

---

## Self-Review

### Done correctly
- Protocol signatures match brief verbatim
- Error hierarchy as specified
- pyproject.toml matches exact brief content
- Config priority env > yaml > defaults verified by test
- No Task 1+ implementation (no sounddevice_io, orchestrator, etc.)
- Plan doc preserved

### Concerns
1. **Push blocked** — local commit exists but remote is empty until network allows `git push -u origin HEAD`
2. **Repo name** — `diet-smart-speaker` used because `smart-speaker` name taken on account
3. **`cli.py` stub** — not listed in Task 0 files but required by `pyproject.toml` `[project.scripts]`; exits with message until Task 7
4. **Default branch** — `master` (git default); not renamed to `main`

### Not in scope (deferred)
- Task 1+ adapters, orchestrator, scripts, manual gates

---

## Manual Follow-up

When network is available:

```bash
cd "/Users/whiteashes/Documents/智能音箱"
git push -u origin HEAD
gh repo view --json isPrivate,url
```

---

## Task 0 Completion Checklist

- [x] git init
- [x] private GitHub repo (`diet-smart-speaker`)
- [x] pyproject.toml, .gitignore, .env.example, config.yaml.example, README.md
- [x] errors.py, config.py, protocols/*, adapters/testing/* shells
- [x] test_protocols_import.py, test_config.py
- [x] pytest 4/4 PASS
- [x] local commit
- [ ] push to origin — **BLOCKED (network)**
