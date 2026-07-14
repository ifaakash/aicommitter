![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)
![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Maintained](https://img.shields.io/badge/Maintained%3F-yes-green.svg)
![GitHub last commit](https://img.shields.io/github/last-commit/ifaakash/ai_commit)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)
![Latest Release](https://img.shields.io/badge/Release-1.0.8-orange)
[![PyPi](https://img.shields.io/pypi/v/aicommitter)](https://pypi.org/project/aicommitter/)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/91b5d92dde4d480b9351b0212fbf725f)](https://app.codacy.com/gh/ifaakash/ai_commit/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
<!--[![Latest Release](https://img.shields.io/badge/Latest-Release-blue?style=for-the-badge)](https://libraries.io/pypi/aicommitter)-->

### One-Time Setup

1. **Obtain your API Key**  
   Register and get an API key from the DeepSeek AI developer dashboard<br>
   - Get DeepSeek API key from [Deepseek Dashboard](https://platform.deepseek.com/api_keys)
   - Get Gemini API key from [Gemini Dashboard](https://aistudio.google.com/api-keys)

2. **Set the Environment Variable**  
   Set your key as the DEEPSEEK_API_KEY environment variable<br>
   ```bash
   export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
   ```

3. **Install the Git Hook in your repository**  
   Navigate to the root of any Git project and run the install command<br>
   ```bash
   aicommitter install
   ```

### Daily Usage
For every commit after setup:

4. **Stage your changes**  
   Add all or selected changes to the staging area<br>
   ```bash
   git add .
   ```

5. **Commit!**  
   Commit directly with confirmation<br>
   ```bash
   aicommitter generate --commit
   ```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a [detailed history](https://libraries.io/pypi/aicommitter) of changes. View on [PyPI](https://pypi.org/project/aicommitter/).

## Latest Release

**Version 1.0.9** (2026-04-25)
- Add `y` flag to auto approve the commit message

**Version 1.0.8** (2026-04-25)
- Fixed `NotOpenSSLWarning` by suppressing it before `urllib3` is imported
- Added `--version` / `-v` flag to CLI

**Version 1.0.7** (2026-04-25)
- Version bump

**Version 1.0.6** (2026-01-25)
- Updated the version of aicommitter to `1.0.6`
- Fixed the issue of `NotOpenSSLWarning` warning

**Version 1.0.5** (2026-01-25)
- Updated the version of aicommitter to `1.0.5`
- Fixed the issue of `docs.md` file not being found
- Fixed the timeout issue
- Swtiched to `deepseek-chat` model from `deepseek-reasoner` model

**Version 1.0.4** (2025-12-07)
- Updated the version of aicommitter to `1.0.4`
- Added support for `long_description` in pypi library

**Version 1.0.4** (2025-12-07)
- Updated the version of aicommitter to `1.0.4`
- Added support for `long_description` in pypi library

**Version 1.0.3** (2025-12-05)
- Updated the version of aicommitter to `1.0.3`
- Refactored exception handling
- Increased the session timeout to `180s` for `DEEPSEEK` and `GEMINI`

For full details, see the [CHANGELOG](CHANGELOG.md).
