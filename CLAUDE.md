# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**aicommitter** is a Python CLI that generates Conventional Commit messages from staged Git diffs using an AI provider (DeepSeek or Gemini). Published on PyPI as `aicommitter`.

## Commands

```bash
pip install -e .                  # editable install for local development

aicommitter generate              # print a suggested message only
aicommitter generate -c           # generate, confirm, commit
aicommitter generate -c -y        # generate and commit without confirmation
aicommitter generate -P -y        # commit without confirmation, then push to current branch
aicommitter generate -p gemini    # force provider
aicommitter generate -m <model>   # override model name
aicommitter install               # write prepare-commit-msg hook into $GIT_DIR/hooks
aicommitter docs                  # print bundled resources/docs.md in a rich panel
aicommitter --version
```

### Build & publish (see `build.md`)

```bash
rm -rf dist/ build/ src/*.egg-info src/aicommitter/*.egg-info   # stale egg-info dirs exist in-tree
python -m build                                                 # needs `pip install build twine`
twine upload dist/*                                             # username __token__, password = PyPI API token
twine upload --repository testpypi dist/*                       # dry run first
```

There are **no tests** in this project. The Pylint workflow (`.github/workflows/pylint.yml`) is permanently disabled via `if: false`, so nothing runs in CI — verify changes by running the CLI against a real staged diff.

## Architecture

Single module, no internal package structure:

- **`src/aicommitter/generate_message.py`** — the entire application: Typer app, provider resolution, both HTTP clients, hook installer
- **`src/aicommitter/resources/docs.md`** — text shown by `aicommitter docs`, loaded via `importlib.resources.files()`, so it must stay declared in `[tool.setuptools.package-data]`
- **`hooks/prepare-commit`** — a reference copy of the hook. The installer writes from the `HOOK_SCRIPT_CONTENT` string literal in `generate_message.py`, *not* from this file; changing the hook means editing both

### Flow

`cli_generate()` → `get_diff()` (`git diff --cached`; exits 0 when empty) → provider/key/model resolution → `generate_message()` dispatch → `call_deepseek()` or `call_gemini()` → optional `git commit -m` → optional `git push origin <current-branch>`.

### Provider resolution

Explicit `--provider` requires the matching env var and errors out if absent. Otherwise auto-detect: `DEEPSEEK_API_KEY` wins over `GEMINI_API_KEY` when both are set (prints an info line). No key at all → exit 1. Defaults: `deepseek-chat`, `gemini-2.5-flash-lite`.

### Flag coupling

`--push` implies `--commit`. `--yes` only bypasses the confirm prompt — without `--commit`/`--push` it does nothing, since the commit branch is never entered.

### Error-handling asymmetry

`call_deepseek()` swallows request exceptions and **returns an error string as if it were the commit message**. `call_gemini()` lets `raise_for_status()` propagate to the `RequestException` handler in `generate_message()`. Any change to provider error handling should reckon with this difference rather than copying either side blindly.

## Gotchas

- **Import order is load-bearing.** Lines 1–12 of `generate_message.py` call `warnings.filterwarnings(..., NotOpenSSLWarning)` *before* `import requests`. Moving the `requests`/`typer` imports above the filter re-introduces the LibreSSL warning on macOS system Python — this was shipped as a bug fix twice.
- **`load_dotenv(override=True)`** means a `.env` in the working directory silently beats exported shell env vars. There is an untracked `.env` in this repo.
- **Retries are HTTPS-only.** The `Retry` adapter is mounted on `https://` alone (3 retries, backoff 1, on 429/500/502/503/504); request timeout is 120s.

## Version Management

`pyproject.toml` is the single source of truth — `--version` reads installed distribution metadata via `importlib.metadata.version("aicommitter")`, and `src/aicommitter/__init__.py` is intentionally empty. After bumping the version, re-run `pip install -e .` or `--version` still reports the previously installed value.

The docs are *not* auto-derived and currently drift: `pyproject.toml` is at `1.1.0`, `README.md` badge and "Latest Release" say `1.0.9`, and `CHANGELOG.md`'s badge says `1.2.0` while its newest entry is `1.0.8`. A release means updating all four spots (pyproject, README badge, README "Latest Release", CHANGELOG entry).
