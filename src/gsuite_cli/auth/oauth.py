"""OAuth 2.0 flow implementation supporting browser loopback and headless out-of-band flows."""

from __future__ import annotations

import os
import sys
import urllib.parse
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gsuite_cli.config import CLIENT_SECRET_FILE
from gsuite_cli.exceptions import AuthError, ConfigError


def get_client_secret_path(custom_path: str | None = None) -> Path:
    """Resolve path to client_secret.json and verify it exists."""
    path = Path(os.path.expanduser(custom_path)) if custom_path else CLIENT_SECRET_FILE
    if not path.exists():
        raise ConfigError(
            f"OAuth client secrets file not found at {path}.\n"
            "Please create a Google Cloud Project with OAuth 2.0 Desktop Application credentials,\n"
            f"download the credentials JSON, and place it at {path}.",
            details={"expected_path": str(path)},
        )
    return path


def run_loopback_flow(
    client_secret_path: Path,
    scopes: list[str],
    port: int = 0,
) -> Credentials:
    """Run interactive OAuth flow with local loopback web server."""
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            scopes=scopes,
        )
        # prompt='consent' and access_type='offline' ensure we always get a refresh token
        credentials = flow.run_local_server(
            port=port,
            prompt="consent",
            access_type="offline",
            authorization_prompt_message=(
                "Opening your browser for authorization...\n"
                "If browser does not open, visit this URL:\n{url}"
            ),
            success_message=(
                "Authentication successful! You can now close this tab and return to the terminal."
            ),
        )
        return credentials
    except Exception as e:
        raise AuthError(f"Interactive browser authorization failed: {e}")


def run_headless_flow(
    client_secret_path: Path,
    scopes: list[str],
    callback_port: int = 8085,
) -> Credentials:
    """Run headless authorization for SSH and Android Termux environments.

    Instructs the user to open the authorization URL in any browser.
    Once Google redirects to http://localhost:<port>/?code=... (which may fail to load
    in the external browser), the user copies and pastes the redirect URL or authorization
    code back into the terminal.
    """
    redirect_uri = f"http://localhost:{callback_port}/"
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            scopes=scopes,
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
        )

        sys.stdout.write("\n" + "=" * 70 + "\n")
        sys.stdout.write("HEADLESS OAUTH AUTHORIZATION\n")
        sys.stdout.write("=" * 70 + "\n\n")
        sys.stdout.write("1. Open the following URL in any browser (laptop, phone, etc.):\n\n")
        sys.stdout.write(f"   {auth_url}\n\n")
        sys.stdout.write("2. Complete the Google login and grant the requested permissions.\n")
        sys.stdout.write(
            f"3. The browser will redirect to a URL starting with {redirect_uri}\n"
            "   (It may show 'Unable to connect' or 'Site can't be reached' — this is normal!)\n"
        )
        sys.stdout.write("4. Copy the FULL redirect URL from your browser's address bar\n")
        sys.stdout.write("   (or just the 'code=' query parameter) and paste it below.\n\n")

        user_input = input("Paste redirect URL or authorization code here: ").strip()

        if not user_input:
            raise AuthError("Authorization aborted: No input provided.")

        code = extract_auth_code(user_input)
        flow.fetch_token(code=code)
        return flow.credentials
    except Exception as e:
        if isinstance(e, AuthError):
            raise
        raise AuthError(f"Headless authorization failed: {e}")


def extract_auth_code(input_str: str) -> str:
    """Extract authorization code from a raw code string or full redirect URL."""
    input_str = input_str.strip()
    if input_str.startswith("http://") or input_str.startswith("https://"):
        parsed = urllib.parse.urlparse(input_str)
        params = urllib.parse.parse_qs(parsed.query)
        if params.get("code"):
            return params["code"][0]
        raise AuthError(f"Could not find 'code' query parameter in provided URL: {input_str}")
    return input_str


def authenticate_account(
    email: str,
    scopes: list[str],
    headless: bool = False,
    client_secret_path: Path | None = None,
) -> Credentials:
    """Authenticate an account using loopback or headless flow."""
    secret_path = client_secret_path or get_client_secret_path()

    # Auto-detect headless mode if DISPLAY is unset and stdin is a TTY
    is_headless = headless or (
        not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
    )

    if is_headless:
        return run_headless_flow(secret_path, scopes)
    return run_loopback_flow(secret_path, scopes)
