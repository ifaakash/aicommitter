![Version](https://img.shields.io/badge/version-1.2.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)

### Version History

## [1.2.0] - 2026-09-28
### Added
- Shared `build_prompt()` so DeepSeek and Gemini receive one identical
  Conventional Commit spec (types, scope, imperative subject, 72-char limit)
- `normalize_message()` sanitizer applied at a single call site: strips markdown
  code fences and "here is the commit message" preambles, collapses excess blank
  lines, enforces a blank line between subject and body, drops a trailing period
- Warning on stderr when a generated subject is not a Conventional Commit subject
### Fixed
- Markdown code fences could reach a real commit subject, because only the Gemini
  prompt forbade them and no output was ever validated

## [1.1.0] - 2026-09-18
### Changed
- Removed the obsolete Gemini model; default is now `gemini-2.5-flash-lite`

## [1.0.9] - 2026-04-25
### Added
- `--yes` / `-y` to skip the commit confirmation prompt
- `--push` / `-P` to push to the current branch after committing (implies `--commit`)
- Dynamic versioning via `importlib.metadata`, making `pyproject.toml` the single
  source of truth
- Badge support and a `CHANGELOG.md` reference in `README.md`

## [1.0.8] - 2026-04-25
### Fixed
- Fixed `NotOpenSSLWarning` by suppressing it before `urllib3` is imported
### Added
- Added `--version` / `-v` flag to CLI

## [1.0.7] - 2026-04-25
### Changed
- Version bump

## [1.0.6]
### Fixed
- Fixed the issue of `NotOpenSSLWarning` warning

## [1.0.5]
### Fixed
- Fixed the issue of `docs.md` file not being found
- Fixed the timeout issue
- Swtiched to `deepseek-chat` model from `deepseek-reasoner` model

## [1.0.4]
### Added
- Support for `long_description` in the pypi package

### Refactored
- Removed obsolete files

## [1.0.3]
### Added
- Updated the version of aicommitter to `1.0.3`
- Refactored exception handling
- Increased the session timeout to `180s` for **DEEPSEEK** and ****GEMINI**

## [1.0.2]
### Fixed
- Increased the session timeout to `120s` for **DEEPSEEK** and **GEMINI**
