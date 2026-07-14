# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**aicommitter** is a Python CLI tool that generates Conventional Commit messages from staged Git diffs using AI (DeepSeek or Gemini). Published on PyPI as `aicommitter`.

## Commands

```bash
# Install for local development (editable mode)
pip install -e .

# Run the CLI
aicommitter generate              # generate commit message
aicommitter generate --commit     # generate and commit
aicommitter generate -p gemini    # use specific provider
aicommitter generate -m <model>   # override model name
aicommitter install               # install prepare-commit-msg git hook
aicommitter docs                  # show built-in docs
aicommitter --version             # show version

# Build for PyPI
pip install build
python -m build
```

There are no tests configured in this project. The Pylint GitHub Action exists but is disabled (`if: false`).

## Architecture

Single-module CLI app built with Typer. Everything lives in one file:

- **`src/aicommitter/generate_message.py`** — entire application: CLI commands, API calls, git hook installation
- **`src/aicommitter/resources/docs.md`** — bundled documentation shown via `aicommitter docs`
- **`pyproject.toml`** — package config, dependencies, entry point

### Flow

1. `cli_generate()` is the main entry point (Typer command `generate`)
2. Gets staged diff via `git diff --cached`
3. Resolves AI provider: explicit `--provider` flag, or auto-detects from env vars (`DEEPSEEK_API_KEY` or `GEMINI_API_KEY`; DeepSeek takes priority if both set)
4. Calls `call_deepseek()` or `call_gemini()` with the diff
5. Optionally commits with `git commit -m` if `--commit` flag is set

### Key Details

- Entry point: `aicommitter = "aicommitter.generate_message:app"` (Typer app)
- Uses `requests.Session` with retry logic (3 retries, exponential backoff, 120s timeout)
- Default models: `deepseek-chat` (DeepSeek), `gemini-1.5-flash` (Gemini)
- `install` command writes a `prepare-commit-msg` hook that calls `aicommitter generate` automatically on `git commit`

## Version Management

Version appears in three places that must stay in sync:
1. `pyproject.toml` — `version = "1.0.9"` (canonical)
2. `src/aicommitter/__init__.py` — `__version__` (currently out of sync at `0.0.1`)
3. `src/aicommitter/generate_message.py` — hardcoded in `_version_callback` (currently shows `1.0.8`)
