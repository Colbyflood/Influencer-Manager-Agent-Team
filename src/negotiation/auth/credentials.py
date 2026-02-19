"""Gmail OAuth2 and Google Sheets service account credential management.

Provides helpers for:
- Loading/refreshing Gmail OAuth2 credentials from token.json
- Building the Gmail API service client
- Loading a gspread client via service account credentials
"""

from __future__ import annotations

import os
from pathlib import Path

import google.auth.transport.requests
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import Resource, build

DEFAULT_GMAIL_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

DEFAULT_TOKEN_PATH: str = "token.json"
DEFAULT_CREDENTIALS_PATH: str = "credentials.json"


def get_gmail_credentials(
    token_path: str | Path = DEFAULT_TOKEN_PATH,
    credentials_path: str | Path = DEFAULT_CREDENTIALS_PATH,
    scopes: list[str] | None = None,
) -> Credentials:
    """Load Gmail OAuth2 credentials, refreshing or creating as needed.

    If ``token_path`` exists and the stored credentials are valid (or can be
    refreshed), they are returned directly.  Otherwise an interactive OAuth2
    flow is initiated via ``InstalledAppFlow.run_local_server()``.

    The resulting credentials are persisted to ``token_path`` for future use.

    Args:
        token_path: Path to the cached OAuth2 token file.
        credentials_path: Path to the OAuth2 client-secrets file.
        scopes: OAuth2 scopes to request.  Defaults to
            ``DEFAULT_GMAIL_SCOPES`` (gmail.send + gmail.readonly).

    Returns:
        A ``google.oauth2.credentials.Credentials`` instance ready for API
        calls.
    """
    if scopes is None:
        scopes = DEFAULT_GMAIL_SCOPES

    token_path = Path(token_path)
    credentials_path = Path(credentials_path)
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)  # type: ignore[no-untyped-call]

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
        creds = flow.run_local_server(port=0)

    # Persist the (possibly refreshed) credentials
    token_path.write_text(creds.to_json())
    return creds


def get_gmail_service(
    credentials: Credentials | None = None,
) -> Resource:
    """Build and return a Gmail API v1 service client.

    Args:
        credentials: Pre-loaded OAuth2 credentials.  If ``None``,
            ``get_gmail_credentials()`` is called to obtain them.

    Returns:
        A ``googleapiclient.discovery.Resource`` for the Gmail API v1.
    """
    if credentials is None:
        credentials = get_gmail_credentials()
    return build("gmail", "v1", credentials=credentials)


def get_sheets_client(
    service_account_path: str | Path | None = None,
) -> gspread.Client:
    """Load a gspread client using service account credentials.

    The path to the service account JSON key file is resolved in order:
    1. Explicit ``service_account_path`` argument
    2. ``SHEETS_SERVICE_ACCOUNT_PATH`` environment variable
    3. Default gspread location (``~/.config/gspread/service_account.json``)

    Args:
        service_account_path: Optional explicit path to the service account
            JSON key file.

    Returns:
        An authenticated ``gspread.Client``.
    """
    if service_account_path is not None:
        return gspread.service_account(filename=str(service_account_path))

    env_path = os.environ.get("SHEETS_SERVICE_ACCOUNT_PATH")
    if env_path:
        return gspread.service_account(filename=env_path)

    # Fall back to gspread default (~/.config/gspread/service_account.json)
    return gspread.service_account()
