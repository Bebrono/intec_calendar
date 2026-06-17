from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import PROJECT_ROOT, ensure_project_dirs


SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]
REDIRECT_URI = "http://localhost"
TOKEN_PATH = Path("data/google_token.json")
OAUTH_STATE_PATH = Path("data/google_oauth_state.json")


def create_authorization_url(root: Path = PROJECT_ROOT) -> str:
    ensure_project_dirs(root)
    client_secret_path = find_client_secret_file(root)
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_path),
        SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _write_oauth_state(
        root,
        {
            "client_secret_file": str(client_secret_path.relative_to(root)),
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "code_verifier": flow.code_verifier,
        },
    )
    return authorization_url


def finish_authorization(auth_response_or_code: str, root: Path = PROJECT_ROOT) -> Path:
    ensure_project_dirs(root)
    state_payload = _read_oauth_state(root)
    client_secret_path = root / state_payload["client_secret_file"]
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_path),
        SCOPES,
        redirect_uri=state_payload["redirect_uri"],
        state=state_payload["state"],
        code_verifier=state_payload["code_verifier"],
    )

    value = auth_response_or_code.strip()
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        params = parse_qs(parsed.query)
        received_state = params.get("state", [None])[0]
        expected_state = state_payload["state"]
        if received_state != expected_state:
            raise ValueError("OAuth state mismatch. Generate a new auth URL and retry.")
        flow.fetch_token(code=_extract_code(value))
    else:
        flow.fetch_token(code=_extract_code(value))

    token_path = root / TOKEN_PATH
    token_path.write_text(flow.credentials.to_json(), encoding="utf-8")
    _oauth_state_file(root).unlink(missing_ok=True)
    return token_path


def build_calendar_service(root: Path = PROJECT_ROOT):
    credentials = load_credentials(root)
    return build("calendar", "v3", credentials=credentials)


def load_credentials(root: Path = PROJECT_ROOT) -> Credentials:
    token_path = root / TOKEN_PATH
    if not token_path.exists():
        raise FileNotFoundError(
            "Google token not found. Run `python main.py google auth-url` first."
        )

    token_payload = json.loads(token_path.read_text(encoding="utf-8"))
    granted_scopes = set(token_payload.get("scopes") or [])
    requested_scopes = set(SCOPES)
    if not requested_scopes.issubset(granted_scopes):
        raise RuntimeError(
            "Google token does not have enough scopes. "
            "Re-run `python main.py google auth-url` and finish OAuth again."
        )

    credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        token_path.write_text(credentials.to_json(), encoding="utf-8")

    if not credentials.valid:
        raise RuntimeError(
            "Google token is invalid. Re-run OAuth with `python main.py google auth-url`."
        )
    return credentials


def find_client_secret_file(root: Path = PROJECT_ROOT) -> Path:
    matches = sorted(root.glob("client_secret_*.json"))
    if matches:
        return matches[0]

    fallback = root / "credentials.json"
    if fallback.exists():
        return fallback

    raise FileNotFoundError("Google OAuth client_secret_*.json file not found")


def _extract_code(value: str) -> str:
    parsed = urlparse(value)
    if parsed.query:
        params = parse_qs(parsed.query)
        if params.get("code"):
            return params["code"][0]
    return value


def _oauth_state_file(root: Path) -> Path:
    return root / OAUTH_STATE_PATH


def _write_oauth_state(root: Path, payload: dict) -> None:
    _oauth_state_file(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_oauth_state(root: Path) -> dict:
    path = _oauth_state_file(root)
    if not path.exists():
        raise FileNotFoundError(
            "OAuth state not found. Run `python main.py google auth-url` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))
