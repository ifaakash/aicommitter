import os
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
from dotenv import load_dotenv

load_dotenv(override=True)

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
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

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


def call_deepseek(diff: str, api_key: str, model: str) -> str:
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    prompt = f"""
    You are a helpful assistant that writes concise Git commit messages.
    Write a commit message that describes the following diff, following Conventional Commit format.
    Diff:
    {diff}
    """
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

    prompt = f"""
    You are a helpful assistant that writes concise Git commit messages.
    Write a commit message that describes the following diff, following Conventional Commit format.
    Do not include markdown code blocks (like ```) in the output, just the raw message.

    Diff:
    {diff}
    """

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
            return call_deepseek(diff, api_key, model_name)
        elif provider == AIProvider.GEMINI:
            return call_gemini(diff, api_key, model_name)

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
