![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)
![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Maintained](https://img.shields.io/badge/Maintained%3F-yes-green.svg)
![GitHub last commit](https://img.shields.io/github/last-commit/ifaakash/ai_commit)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)
![Latest Release](https://img.shields.io/badge/Release-1.2.0-orange)
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

## Building & Publishing

For maintainers cutting a release to PyPI.

**Before you build**, bump the version in all four places — they are not derived from each other:
`pyproject.toml`, the release badge above, the [Latest Release](#latest-release) section, and a new `CHANGELOG.md` entry.

Requires the release toolchain: `pip install --upgrade build twine`

1. **Clean stale artifacts**
   Old builds in `dist/` get picked up by `twine upload dist/*` and will publish the wrong version<br>
   ```bash
   rm -rf dist/ build/ src/*.egg-info src/aicommitter/*.egg-info
   ```

2. **Build the distributions**
   Produces both an sdist and a wheel<br>
   ```bash
   python -m build
   ```

3. **Verify what was built**
   Confirm only the new version is present, that `resources/docs.md` is bundled, and that the metadata is valid<br>
   ```bash
   ls dist/
   python -m zipfile -l dist/aicommitter-*-py3-none-any.whl | grep docs.md
   twine check dist/*
   ```
   The `docs.md` check is not optional — it ships only via `[tool.setuptools.package-data]`, and a missing copy is what broke `aicommitter docs` in 1.0.5.

4. **Upload to TestPyPI first (recommended)**
   PyPI versions are immutable, so each version number can only ever be uploaded once<br>
   ```bash
   twine upload --repository testpypi dist/*
   pip install --index-url https://test.pypi.org/simple/ --no-deps aicommitter==<version>
   ```

5. **Publish to PyPI**
   Authenticate with `__token__` as the username and a PyPI API token as the password<br>
   ```bash
   twine upload dist/*
   ```

Create an API token at [pypi.org/manage/account/token](https://pypi.org/manage/account/token/). To avoid re-entering it, store it in `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-xxxxxxxxxxxx
```

<details>
<summary><b>Building inside a virtual environment</b> (recommended, and required on externally managed Python)</summary>

<br>

Most current Python installs — Homebrew, Debian/Ubuntu, and python.org 3.12+ — are marked *externally managed*, so installing the build tools globally fails:

```
error: externally-managed-environment
× This environment is externally managed
```

A virtual environment gives the build its own isolated `site-packages`, so `build` and `twine` never touch your system Python and cannot collide with other projects' dependency versions.

**1. Create the virtual environment** — once per clone. `.venv` is already in `.gitignore`:

```bash
python3 -m venv .venv
```

**2. Install the release toolchain into it:**

```bash
.venv/bin/pip install --upgrade build twine
```

**3. Run the build steps through it** — prefix each command with `.venv/bin/` so the venv's interpreter and tools are used:

```bash
rm -rf dist/ build/ src/*.egg-info src/aicommitter/*.egg-info
.venv/bin/python -m build
.venv/bin/twine check dist/*
.venv/bin/twine upload dist/*
```

Prefixing with `.venv/bin/` works without activating anything. If you would rather activate the environment and drop the prefix:

```bash
source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m build
twine check dist/*
twine upload dist/*
deactivate                    # when finished
```

**Testing the built package in the venv** without publishing it, which also verifies the console entry point:

```bash
.venv/bin/pip install dist/aicommitter-*-py3-none-any.whl
.venv/bin/aicommitter --version
.venv/bin/aicommitter docs
```

Note that `aicommitter --version` reads installed distribution metadata, so after a version bump you must reinstall (`.venv/bin/pip install -e .`) before it reports the new number.

To start over at any point, delete and recreate it — a venv is disposable:

```bash
rm -rf .venv
```

</details>

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a [detailed history](https://libraries.io/pypi/aicommitter) of changes. View on [PyPI](https://pypi.org/project/aicommitter/).

## Latest Release

**Version 1.2.0** (2026-09-28)
- Unified the Conventional Commit prompt across DeepSeek and Gemini
- Added an output sanitizer that strips markdown code fences and preambles
- Warn on stderr when a generated subject is not a Conventional Commit subject

**Version 1.1.0** (2026-09-18)
- Removed the obsolete Gemini model; default is now `gemini-2.5-flash-lite`

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

```bash
aicommitter generate -c -y        # generate, commit without confirmation
aicommitter generate -P -y        # generate, commit without confirmation, push to current branch
aicommitter generate --push       # generate, confirm commit, then push
```
