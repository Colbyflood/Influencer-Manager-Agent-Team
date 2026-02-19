"""Tests for the auth credentials module.

Uses unittest.mock to avoid requiring real Google API credentials.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from negotiation.auth.credentials import (
    DEFAULT_CREDENTIALS_PATH,
    DEFAULT_GMAIL_SCOPES,
    DEFAULT_TOKEN_PATH,
    get_gmail_credentials,
    get_gmail_service,
    get_sheets_client,
)

# ---------------------------------------------------------------------------
# get_gmail_credentials
# ---------------------------------------------------------------------------


class TestGetGmailCredentials:
    """Tests for get_gmail_credentials."""

    @patch("negotiation.auth.credentials.Credentials.from_authorized_user_file")
    def test_loads_existing_valid_token(self, mock_from_file: MagicMock, tmp_path: Path):
        """Returns cached credentials when token.json exists and is valid."""
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_from_file.return_value = mock_creds

        result = get_gmail_credentials(token_path=token_path)

        mock_from_file.assert_called_once_with(str(token_path), DEFAULT_GMAIL_SCOPES)
        assert result is mock_creds

    @patch("negotiation.auth.credentials.Credentials.from_authorized_user_file")
    def test_refreshes_expired_token(self, mock_from_file: MagicMock, tmp_path: Path):
        """Refreshes credentials when token exists but is expired."""
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh-token"
        mock_creds.to_json.return_value = '{"refreshed": true}'
        mock_from_file.return_value = mock_creds

        result = get_gmail_credentials(token_path=token_path)

        mock_creds.refresh.assert_called_once()
        assert result is mock_creds

    @patch("negotiation.auth.credentials.InstalledAppFlow.from_client_secrets_file")
    def test_runs_oauth_flow_when_no_token(self, mock_flow_cls: MagicMock, tmp_path: Path):
        """Initiates OAuth flow when no token.json exists."""
        token_path = tmp_path / "token.json"
        creds_path = tmp_path / "credentials.json"
        creds_path.write_text("{}")

        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "new"}'
        mock_flow.run_local_server.return_value = mock_creds
        mock_flow_cls.return_value = mock_flow

        result = get_gmail_credentials(token_path=token_path, credentials_path=creds_path)

        mock_flow_cls.assert_called_once_with(str(creds_path), DEFAULT_GMAIL_SCOPES)
        mock_flow.run_local_server.assert_called_once_with(port=0)
        assert result is mock_creds

    @patch("negotiation.auth.credentials.InstalledAppFlow.from_client_secrets_file")
    def test_persists_new_token(self, mock_flow_cls: MagicMock, tmp_path: Path):
        """Saves new credentials to token_path after OAuth flow."""
        token_path = tmp_path / "token.json"
        creds_path = tmp_path / "credentials.json"
        creds_path.write_text("{}")

        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "persisted"}'
        mock_flow.run_local_server.return_value = mock_creds
        mock_flow_cls.return_value = mock_flow

        get_gmail_credentials(token_path=token_path, credentials_path=creds_path)

        assert token_path.exists()
        assert token_path.read_text() == '{"token": "persisted"}'

    @patch("negotiation.auth.credentials.Credentials.from_authorized_user_file")
    def test_custom_scopes(self, mock_from_file: MagicMock, tmp_path: Path):
        """Passes custom scopes to credential loading."""
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_from_file.return_value = mock_creds

        custom_scopes = ["https://www.googleapis.com/auth/gmail.send"]
        get_gmail_credentials(token_path=token_path, scopes=custom_scopes)

        mock_from_file.assert_called_once_with(str(token_path), custom_scopes)

    def test_default_constants(self):
        """Default constants have expected values."""
        assert DEFAULT_TOKEN_PATH == "token.json"
        assert DEFAULT_CREDENTIALS_PATH == "credentials.json"
        assert len(DEFAULT_GMAIL_SCOPES) == 2
        assert "gmail.send" in DEFAULT_GMAIL_SCOPES[0]
        assert "gmail.readonly" in DEFAULT_GMAIL_SCOPES[1]

    @patch("negotiation.auth.credentials.Credentials.from_authorized_user_file")
    @patch("negotiation.auth.credentials.InstalledAppFlow.from_client_secrets_file")
    def test_runs_flow_when_expired_without_refresh_token(
        self, mock_flow_cls: MagicMock, mock_from_file: MagicMock, tmp_path: Path
    ):
        """Initiates OAuth flow when token is expired and has no refresh token."""
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")
        creds_path = tmp_path / "credentials.json"
        creds_path.write_text("{}")

        mock_creds_old = MagicMock()
        mock_creds_old.valid = False
        mock_creds_old.expired = True
        mock_creds_old.refresh_token = None
        mock_from_file.return_value = mock_creds_old

        mock_flow = MagicMock()
        mock_creds_new = MagicMock()
        mock_creds_new.to_json.return_value = '{"new": true}'
        mock_flow.run_local_server.return_value = mock_creds_new
        mock_flow_cls.return_value = mock_flow

        result = get_gmail_credentials(
            token_path=token_path,
            credentials_path=creds_path,
        )

        mock_flow.run_local_server.assert_called_once()
        assert result is mock_creds_new


# ---------------------------------------------------------------------------
# get_gmail_service
# ---------------------------------------------------------------------------


class TestGetGmailService:
    """Tests for get_gmail_service."""

    @patch("negotiation.auth.credentials.build")
    def test_builds_gmail_v1_service(self, mock_build: MagicMock):
        """Builds Gmail API v1 with provided credentials."""
        mock_creds = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        result = get_gmail_service(credentials=mock_creds)

        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
        assert result is mock_service

    @patch("negotiation.auth.credentials.get_gmail_credentials")
    @patch("negotiation.auth.credentials.build")
    def test_auto_loads_credentials_when_none(
        self, mock_build: MagicMock, mock_get_creds: MagicMock
    ):
        """Calls get_gmail_credentials when no credentials supplied."""
        mock_creds = MagicMock()
        mock_get_creds.return_value = mock_creds

        get_gmail_service(credentials=None)

        mock_get_creds.assert_called_once()
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)


# ---------------------------------------------------------------------------
# get_sheets_client
# ---------------------------------------------------------------------------


class TestGetSheetsClient:
    """Tests for get_sheets_client."""

    @patch("negotiation.auth.credentials.gspread.service_account")
    def test_explicit_path(self, mock_sa: MagicMock, tmp_path: Path):
        """Uses explicit service_account_path when provided."""
        sa_path = tmp_path / "sa.json"
        get_sheets_client(service_account_path=sa_path)
        mock_sa.assert_called_once_with(filename=str(sa_path))

    @patch.dict("os.environ", {"SHEETS_SERVICE_ACCOUNT_PATH": "/env/sa.json"})
    @patch("negotiation.auth.credentials.gspread.service_account")
    def test_env_var_path(self, mock_sa: MagicMock):
        """Uses SHEETS_SERVICE_ACCOUNT_PATH env var when no explicit path."""
        get_sheets_client()
        mock_sa.assert_called_once_with(filename="/env/sa.json")

    @patch.dict("os.environ", {}, clear=True)
    @patch("negotiation.auth.credentials.gspread.service_account")
    def test_default_gspread_path(self, mock_sa: MagicMock):
        """Falls back to gspread default when no path specified."""
        get_sheets_client()
        mock_sa.assert_called_once_with()

    @patch("negotiation.auth.credentials.gspread.service_account")
    def test_returns_client(self, mock_sa: MagicMock):
        """Returns the gspread Client instance."""
        mock_client = MagicMock()
        mock_sa.return_value = mock_client

        result = get_sheets_client(service_account_path="/some/path.json")
        assert result is mock_client
