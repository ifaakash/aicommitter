import os
import re
import subprocess
import warnings
from enum import Enum
from subprocess import DEVNULL
from importlib import resources
from importlib.metadata import version as pkg_version
from urllib3.exceptions import NotOpenSSLWarning

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import typer
from rich import print
from rich.panel import Panel
from dotenv import load_dotenv, dotenv_values, find_dotenv

# Snapshot the shell's own values before .env can override them, so doctor can
# report when a .env entry is shadowing an exported key.
_PRE_DOTENV_ENV = {
    name: os.getenv(name) for name in ("DEEPSEEK_API_KEY", "GEMINI_API_KEY")
}
# find_dotenv() resolves relative to this file's directory tree, not the CWD,
# so an editable install always picks up the repo's own .env.
DOTENV_PATH = find_dotenv()
load_dotenv(DOTENV_PATH, override=True)

app = typer.Typer(
    help="AI Commit Message Generator. Reads staged Git diff and suggests a message"
)

def _version_callback(value: bool):
    if value:
        typer.echo(f"aicommitter {pkg_version('aicommitter')}")
        raise typer.Exit()

@app.callback()
def _main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=_version_callback, is_eager=True, help="Show version and exit."
    )
):
    pass

SESSION = requests.Session()
retries = Retry(
    total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
)
SESSION.mount("https://", HTTPAdapter(max_retries=retries))

DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"

CONVENTIONAL_TYPES = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)
SUBJECT_MAX_LEN = 72
SUBJECT_RE = re.compile(
    r"^(?:" + "|".join(CONVENTIONAL_TYPES) + r")(?:\([^)]+\))?!?: .+"
)

_FENCE_RE = re.compile(r"^```[\w-]*\s*$")
_PREAMBLE_RE = re.compile(
    r"^(?:here(?:'s| is)|commit message|suggested commit message)\b.*:\s*$",
    re.IGNORECASE,
)

HOOK_SCRIPT_CONTENT = """#!/usr/bin/env bash
COMMIT_MSG_FILE=$1
echo "--- Prepare-Commit-Message Hook Triggered ---" > /dev/tty
cd "$(git rev-parse --show-toplevel)" || exit 1
EXISTING_MSG=$(grep -v '^#' "$COMMIT_MSG_FILE" | head -n 1 | tr -d '[:space:]')
if [[ -n "$EXISTING_MSG" ]]; then
    echo "INFO: User provided an existing message. Skipping AI generation." > /dev/tty
    exit 0
fi
set -e
GENERATED_MSG=$(aicommitter generate)
set +e
if [[ -z "$(echo "$GENERATED_MSG" | tr -d '[:space:]')" ]]; then
    echo "ERROR: Generated message is empty. Manual edit required." > /dev/tty
    exit 1
fi
echo "$GENERATED_MSG" > "$COMMIT_MSG_FILE"
echo "INFO: Successfully generated and set the commit message." > /dev/tty
echo "--- Generated Message ---" > /dev/tty
echo "$GENERATED_MSG" > /dev/tty
echo "-------------------------" > /dev/tty
exit 0
"""


class AIProvider(str, Enum):
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"

def get_readme_content(filename: str = "docs.md") -> str:
    return (
        resources
        .files("aicommitter.resources")
        .joinpath(filename)
        .read_text()
    )

@app.command(name="docs")
def show_docs():
    try:
        content = get_readme_content()

        print(
            Panel(
                content,
                title="aicommitter docs",
                border_style="green",
            )
        )

    except FileNotFoundError:
        print("[bold red]Error:[/bold red] Documentation file not found.")

    except Exception as e:
        print(f"[bold red]Error reading docs:[/bold red] {e}")

@app.command(name="install")
def install_hook():
    """Installs the prepare-commit-msg hook in the current Git repository."""
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()

        hook_path = os.path.join(git_dir, "hooks", "prepare-commit-msg")
        with open(hook_path, "w") as f:
            f.write(HOOK_SCRIPT_CONTENT)
        os.chmod(hook_path, 0o755)

        typer.echo(
            typer.style(
                f"\nSuccessfully installed hook in {hook_path}",
                fg=typer.colors.GREEN,
                bold=True,
            )
        )
        typer.echo("Run 'git commit' in this repository to test.")

    except subprocess.CalledProcessError:
        typer.echo(
            typer.style("ERROR: Not in a Git repository.", fg=typer.colors.RED),
            err=True,
        )
        raise typer.Exit(code=1)


PROVIDER_KEYS = {
    AIProvider.DEEPSEEK: {
        "env": "DEEPSEEK_API_KEY",
        "label": "DeepSeek",
        "console": "https://platform.deepseek.com/api_keys",
        "models_url": "https://api.deepseek.com/models",
    },
    AIProvider.GEMINI: {
        "env": "GEMINI_API_KEY",
        "label": "Gemini",
        "console": "https://aistudio.google.com/api-keys",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/models",
    },
}


def _mask(value: str) -> str:
    """Renders a key for display without disclosing it."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}{'*' * 6}{value[-4:]}"


def _key_source(env_name: str) -> str:
    """Reports which .env file or environment a key actually came from.

    load_dotenv(override=True) means a .env value silently beats an exported
    one, so the distinction matters when diagnosing a stale key.
    """
    if DOTENV_PATH:
        try:
            if env_name in dotenv_values(DOTENV_PATH):
                return f".env ({DOTENV_PATH})"
        except OSError:
            pass
    return "shell environment"


def _is_shadowing(env_name: str) -> bool:
    """True when a .env entry replaced a different exported value."""
    previous = _PRE_DOTENV_ENV.get(env_name)
    return bool(previous) and previous != os.getenv(env_name)


def _probe_key(provider: AIProvider, api_key: str) -> str:
    """Asks the provider whether the key is actually accepted."""
    meta = PROVIDER_KEYS[provider]
    try:
        if provider == AIProvider.DEEPSEEK:
            response = SESSION.get(
                meta["models_url"],
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
        else:
            response = SESSION.get(
                meta["models_url"], params={"key": api_key}, timeout=30
            )
    except requests.exceptions.RequestException as e:
        return f"unreachable ({e.__class__.__name__})"

    if response.status_code == 200:
        return "accepted"
    # A plain model-list GET only fails this way when the key is unacceptable:
    # DeepSeek answers 401, Gemini answers 400 for a malformed key and 403 for
    # one that is well formed but unauthorised.
    if response.status_code in (400, 401, 403):
        return f"REJECTED (HTTP {response.status_code} - key invalid or revoked)"
    return f"unexpected HTTP {response.status_code}"


def _print_setup_help() -> None:
    """Prints how to obtain and set a key."""
    typer.echo("\nTo set one up, get a key from either provider:\n")
    for meta in PROVIDER_KEYS.values():
        typer.echo(f"  {meta['label']:<9} {meta['console']}")

    typer.echo("\nThen make it available. For the current shell only:\n")
    typer.echo('  export DEEPSEEK_API_KEY="sk-..."')

    typer.echo("\nTo persist it across sessions (zsh, the macOS default):\n")
    typer.echo('  echo \'export DEEPSEEK_API_KEY="sk-..."\' >> ~/.zshrc')
    typer.echo("  source ~/.zshrc")
    typer.echo("\n  ...or ~/.bashrc if you use bash.")

    typer.echo("\nOr per project, in a .env file at the repository root:\n")
    typer.echo("  echo 'DEEPSEEK_API_KEY=sk-...' >> .env")
    typer.echo(
        "\nNote: a .env value overrides an exported shell variable, so remove a "
        "stale\nkey from .env if it is shadowing a working one."
    )
    typer.echo("\nRe-run 'aicommitter doctor' to confirm.")


@app.command(name="doctor")
def doctor(
    live: bool = typer.Option(
        False,
        "--live",
        "-l",
        help="Also ask each provider whether the key is actually accepted.",
    )
):
    """Checks whether an AI provider API key is configured."""

    typer.echo("\nProvider keys")

    found = {}
    for provider, meta in PROVIDER_KEYS.items():
        env_name = meta["env"]
        value = os.getenv(env_name)
        if value:
            found[provider] = value
            typer.echo(
                f"  {env_name:<18} "
                + typer.style("set", fg=typer.colors.GREEN, bold=True)
                + f"      {_mask(value)}  (from {_key_source(env_name)})"
            )
            if _is_shadowing(env_name):
                typer.echo(
                    "  "
                    + typer.style(
                        f"{'':<18} note: this .env entry overrides the "
                        f"{env_name} exported in your shell",
                        fg=typer.colors.YELLOW,
                    )
                )
        else:
            typer.echo(
                f"  {env_name:<18} "
                + typer.style("missing", fg=typer.colors.YELLOW)
            )

    if not found:
        typer.echo(
            "\n"
            + typer.style(
                "No API key found - aicommitter cannot generate messages.",
                fg=typer.colors.RED,
                bold=True,
            )
        )
        _print_setup_help()
        raise typer.Exit(code=1)

    # Mirrors the resolution order in cli_generate(): DeepSeek wins a tie.
    active = (
        AIProvider.DEEPSEEK if AIProvider.DEEPSEEK in found else AIProvider.GEMINI
    )
    default_model = (
        DEFAULT_DEEPSEEK_MODEL
        if active == AIProvider.DEEPSEEK
        else DEFAULT_GEMINI_MODEL
    )
    typer.echo(
        f"\nActive provider\n  {PROVIDER_KEYS[active]['label']} ({default_model})"
    )
    if len(found) > 1:
        typer.echo(
            "  Both keys are set; DeepSeek takes priority. "
            "Use --provider gemini to switch."
        )

    if live:
        typer.echo("\nLive key check")
        rejected = False
        for provider, value in found.items():
            result = _probe_key(provider, value)
            colour = (
                typer.colors.GREEN if result == "accepted" else typer.colors.RED
            )
            rejected = rejected or result != "accepted"
            typer.echo(
                f"  {PROVIDER_KEYS[provider]['label']:<9} "
                + typer.style(result, fg=colour)
            )
        if rejected:
            typer.echo(
                "\n"
                + typer.style(
                    "A key is set but not usable. Replace it, then re-run with --live.",
                    fg=typer.colors.RED,
                )
            )
            _print_setup_help()
            raise typer.Exit(code=1)
    else:
        typer.echo(
            "\nKeys are present but not verified. "
            "Run 'aicommitter doctor --live' to test them."
        )

    typer.echo(
        "\n" + typer.style("Ready to generate.", fg=typer.colors.GREEN, bold=True)
    )


def get_diff() -> str:
    """Runs 'git diff --cached' and handles errors."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=DEVNULL,
            stderr=DEVNULL,
            check=True,
        )
        diff = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            check=True,
        )
        return diff.stdout
    except subprocess.CalledProcessError:
        typer.echo("Error: Git command failed. Are you in a Git repository?", err=True)
        return ""
    except FileNotFoundError:
        typer.echo("Error: 'git' command not found.", err=True)
        return ""


def build_prompt(diff: str) -> str:
    """The single Conventional Commit spec shared by every provider."""
    return f"""You write Git commit messages that follow the Conventional Commits specification.

Write one commit message describing the diff below.

Subject line:
- format: <type>(<optional scope>): <description>
- type must be one of: {", ".join(CONVENTIONAL_TYPES)}
- use the imperative mood ("add", not "added" or "adds")
- start the description in lowercase and do not end it with a period
- keep the whole subject line under {SUBJECT_MAX_LEN} characters

Body (optional, include only when the change needs explanation):
- separate it from the subject with one blank line
- wrap lines at 72 characters
- use "- " bullets for distinct changes

Output rules:
- output the raw commit message only
- no markdown code fences and no backticks around the message
- no preamble, commentary, or explanation of your answer

Diff:
{diff}
"""


def normalize_message(raw: str) -> str:
    """Strips model chatter (fences, preambles) and fixes commit layout."""
    text = (raw or "").strip()
    if not text:
        return ""

    lines = text.splitlines()

    # Unfence: ```, ```text or ```gitcommit wrapping the whole message.
    if lines and _FENCE_RE.match(lines[0]):
        lines = lines[1:]
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and _FENCE_RE.match(lines[-1]):
            lines.pop()

    # Drop a leading "Here is the commit message:" style preamble.
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and _PREAMBLE_RE.match(lines[0].strip()):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)

    if not lines:
        return ""

    # Subject carries no trailing period.
    subject = lines[0].strip()
    if subject.endswith(".") and not subject.endswith("..."):
        subject = subject[:-1]
    lines[0] = subject

    # A body must be separated from the subject by exactly one blank line.
    if len(lines) > 1 and lines[1].strip():
        lines.insert(1, "")

    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def call_deepseek(diff: str, api_key: str, model: str) -> str:
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    prompt = build_prompt(diff)
    data = {
        "model": model,
        "messages": [{"role": "system", "content": prompt}],
        "stream": False,
    }
    try:
        response = SESSION.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        return (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
    except requests.exceptions.Timeout:
        return "Error: Request timed out after 120 seconds"
    except requests.exceptions.HTTPError as e:
        return f"Error: HTTP {e.response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"


def call_gemini(diff: str, api_key: str, model: str) -> str:
    # Google Generative AI REST API Endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}

    prompt = build_prompt(diff)

    # Gemini payload structure
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    response = SESSION.post(url, headers=headers, json=data, timeout=120)

    # Detailed error handling for Google API
    if response.status_code != 200:
        typer.echo(f"Gemini API Error: {response.text}", err=True)
        response.raise_for_status()

    result = response.json()
    try:
        # Navigate Gemini's JSON response structure
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        typer.echo(f"Error parsing Gemini response: {result}", err=True)
        return ""


# Generate the commit message
def generate_message(
    diff: str, provider: AIProvider, api_key: str, model_name: str
) -> str:
    """Dispatches the generation request to the correct provider"""

    try:
        typer.echo(
            f"... Calling {provider.value.title()} ({model_name}) for generation ..."
        )

        if provider == AIProvider.DEEPSEEK:
            raw = call_deepseek(diff, api_key, model_name)
        elif provider == AIProvider.GEMINI:
            raw = call_gemini(diff, api_key, model_name)
        else:
            return ""

        message = normalize_message(raw)
        if message and not SUBJECT_RE.match(message.splitlines()[0]):
            typer.echo(
                "Warning: subject is not a Conventional Commit subject "
                "(<type>(<scope>): <description>, type one of "
                f"{', '.join(CONVENTIONAL_TYPES)}).",
                err=True,
            )
        return message

    except requests.exceptions.RequestException as e:
        typer.echo(f"Error: API request failed. {e}", err=True)
        return ""
    return ""


# Entry point for application
@app.command(name="generate")
def cli_generate(
    commit: bool = typer.Option(
        False,
        "--commit",
        "-c",
        help="Immediately commit the suggested message if confirmed.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation and commit immediately.",
    ),
    push: bool = typer.Option(
        False,
        "--push",
        "-P",
        help="Push to current branch after committing.",
    ),
    provider: str = typer.Option(
        None, "--provider", "-p", help="Explicitly choose 'deepseek' or 'gemini'."
    ),
    model: str = typer.Option(
        None, "--model", "-m", help="Override the default model name."
    ),
):
    """
    Generates a Conventional Commit message.
    Automatically detects DEEPSEEK_API_KEY or GEMINI_API_KEY.
    """

    if push:
        commit = True

    diff = get_diff()
    if not diff.strip():
        typer.echo("INFO: No staged changes found.")
        raise typer.Exit(code=0)

    # --- [NEW] Provider and Key Resolution Logic ---
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    selected_provider = None
    selected_key = None
    selected_model = model  # User override or default

    # Logic 1: User explicitly asked for a provider
    if provider:
        if provider.lower() == "deepseek":
            if not deepseek_key:
                typer.echo(
                    "Error: --provider is deepseek but DEEPSEEK_API_KEY is not set.",
                    err=True,
                )
                raise typer.Exit(1)
            selected_provider = AIProvider.DEEPSEEK
            selected_key = deepseek_key
            if not selected_model:
                selected_model = DEFAULT_DEEPSEEK_MODEL

        elif provider.lower() == "gemini":
            if not gemini_key:
                typer.echo(
                    "Error: --provider is gemini but GEMINI_API_KEY is not set.",
                    err=True,
                )
                raise typer.Exit(1)
            selected_provider = AIProvider.GEMINI
            selected_key = gemini_key
            if not selected_model:
                selected_model = DEFAULT_GEMINI_MODEL
        else:
            typer.echo(
                f"Error: Unknown provider '{provider}'. Use 'deepseek' or 'gemini'.",
                err=True,
            )
            raise typer.Exit(1)

    # Logic 2: Auto-detect based on env vars
    else:
        if deepseek_key:
            selected_provider = AIProvider.DEEPSEEK
            selected_key = deepseek_key
            if not selected_model:
                selected_model = DEFAULT_DEEPSEEK_MODEL
            # If both exist, we default to DeepSeek unless specific logic changes
            if gemini_key:
                typer.echo(
                    "Info: Both keys found. Defaulting to DeepSeek. Use --provider gemini to switch."
                )

        elif gemini_key:
            selected_provider = AIProvider.GEMINI
            selected_key = gemini_key
            if not selected_model:
                selected_model = DEFAULT_GEMINI_MODEL

        else:
            typer.echo(
                "Error: No API keys found. Please export DEEPSEEK_API_KEY or GEMINI_API_KEY.",
                err=True,
            )
            raise typer.Exit(1)

    # --- Execute Generation ---
    commit_message = generate_message(
        diff, selected_provider, selected_key, selected_model
    )

    if not commit_message:
        raise typer.Exit(code=1)

    typer.echo("\n" + "=" * 50)
    typer.echo(f"Suggested Commit Message ({selected_provider.value}):")
    typer.echo(commit_message)
    typer.echo("=" * 50 + "\n")

    if commit:
        confirm = yes or typer.confirm("Do you want to use this message to commit?")
        if confirm:
            try:
                subprocess.run(["git", "commit", "-m", commit_message], check=True)
                typer.echo(
                    typer.style("Commit successful!", fg=typer.colors.GREEN, bold=True)
                )
            except subprocess.CalledProcessError:
                typer.echo("Error: Git commit failed.", err=True)
                raise typer.Exit(code=1)
            if push:
                try:
                    branch = subprocess.run(
                        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True, text=True, check=True
                    ).stdout.strip()
                    subprocess.run(["git", "push", "origin", branch], check=True)
                    typer.echo(
                        typer.style(f"Pushed to origin/{branch}!", fg=typer.colors.GREEN, bold=True)
                    )
                except subprocess.CalledProcessError:
                    typer.echo("Error: Git push failed.", err=True)
                    raise typer.Exit(code=1)
        else:
            typer.echo("Commit aborted by user.")
            raise typer.Exit()
    else:
        typer.echo("Message generated. Run with '-c' to commit automatically.")


if __name__ == "__main__":
    try:
        app()
    finally:
        SESSION.close()
