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
aicommitter doctor                # check API key setup; exits 1 if unusable
aicommitter doctor --live         # also verify the key against the provider
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

`doctor` mirrors this same order and must be kept in step with `cli_generate()` if it changes. Provider env var names, consoles, and probe URLs live in one table, `PROVIDER_KEYS` — add a provider there, not inline.

### Flag coupling

`--push` implies `--commit`. `--yes` only bypasses the confirm prompt — without `--commit`/`--push` it does nothing, since the commit branch is never entered.

### Message formatting

Format is specified in exactly one place: `build_prompt()` builds the Conventional Commit spec (allowed types from `CONVENTIONAL_TYPES`, imperative subject, `SUBJECT_MAX_LEN` = 72, no fences/preamble) and both providers send that same text — DeepSeek as its single `system` message, Gemini as its single `contents[0].parts[0].text`.

Every generated message then passes `normalize_message()`, called once in `generate_message()` around the dispatch so no provider can bypass it: unfence, de-preamble, collapse blank-line runs, force a blank line between subject and body, drop a trailing period. If the result's subject fails `SUBJECT_RE`, a warning goes to **stderr** and the message is still returned — a hard failure would break `-y` automation, and stderr keeps the stdout contract the hook depends on intact.

Add format rules to `build_prompt()` (what the model should do) and repairs to `normalize_message()` (what to fix when it doesn't). Do not add either to a provider function.

### Error-handling asymmetry

`call_deepseek()` swallows request exceptions and **returns an error string as if it were the commit message**. `call_gemini()` lets `raise_for_status()` propagate to the `RequestException` handler in `generate_message()`. The subject validation above now warns on those DeepSeek error strings, but does not stop them being committed — the asymmetry itself is still unfixed.

## Gotchas

- **Import order is load-bearing.** Lines 1–12 of `generate_message.py` call `warnings.filterwarnings(..., NotOpenSSLWarning)` *before* `import requests`. Moving the `requests`/`typer` imports above the filter re-introduces the LibreSSL warning on macOS system Python — this was shipped as a bug fix twice.
- **`load_dotenv(override=True)`** means a `.env` value silently beats an exported shell var. Worse, `find_dotenv()` resolves relative to **`generate_message.py`'s own directory tree, not your CWD** — so in an editable install the repo's untracked `.env` applies no matter where you run `aicommitter`. That `.env` currently holds a DeepSeek key returning HTTP 401; `aicommitter doctor` names the exact file and flags the shadowing.
- **Retries are HTTPS-only.** The `Retry` adapter is mounted on `https://` alone (3 retries, backoff 1, on 429/500/502/503/504); request timeout is 120s.

## Version Management

`pyproject.toml` is the single source of truth — `--version` reads installed distribution metadata via `importlib.metadata.version("aicommitter")`, and `src/aicommitter/__init__.py` is intentionally empty. After bumping the version, re-run `pip install -e .` or `--version` still reports the previously installed value.

The docs are *not* auto-derived, so a release means updating four spots by hand, all currently at `1.2.0`: `pyproject.toml`, the `README.md` badge, the README "Latest Release" section, and a `CHANGELOG.md` entry (plus its own version badge). These drifted apart across 1.0.9-1.1.0; keep them in step.
