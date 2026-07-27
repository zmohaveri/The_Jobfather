"""
Google Docs tools — read, create, and edit documents via the Google Docs API.

Uses OAuth 2.0 Desktop flow (no API key needed).
Requires a ``credentials.json`` file downloaded from Google Cloud Console.
A ``token.json`` is auto-generated on first run after browser consent.

These functions are designed to be callable by a chat agent.
"""

import json
import re
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── Paths & scopes ───────────────────────────────────────────────────

_BASE = Path(__file__).resolve().parent.parent.parent
_CREDENTIALS_FILE = _BASE / "credentials.json"
_TOKEN_FILE = _BASE / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


# ── Auth ─────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    """Load or create OAuth2 credentials (opens browser on first run)."""
    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"OAuth credentials file not found at {_CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console → APIs & Services → Credentials "
                    "(OAuth 2.0 Client ID, Desktop app) and save it as credentials.json "
                    "in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        _TOKEN_FILE.write_text(creds.to_json())

    return creds


def _docs_service():
    """Return an authenticated Google Docs API service."""
    return build("docs", "v1", credentials=_get_credentials())


def _drive_service():
    """Return an authenticated Google Drive API service (for sharing)."""
    return build("drive", "v3", credentials=_get_credentials())


# ── Helpers ──────────────────────────────────────────────────────────

def _extract_doc_id(doc_id_or_url: str) -> str:
    """Accept a document ID or a full Google Docs URL and return just the ID."""
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", doc_id_or_url)
    if m:
        return m.group(1)
    return doc_id_or_url.strip()


def _extract_plain_text(body: dict) -> str:
    """Walk the document body and return plain text."""
    parts: list[str] = []
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for run in paragraph.get("elements", []):
            text_run = run.get("textRun")
            if text_run:
                parts.append(text_run["content"])
    return "".join(parts)


# ── Tools ────────────────────────────────────────────────────────────

def read_document(doc_id_or_url: str) -> dict:
    """
    Read a Google Doc and return its title, plain-text body, and document ID.

    Args:
        doc_id_or_url: Google Docs document ID or full URL.

    Returns:
        dict with keys: document_id, title, text
    """
    doc_id = _extract_doc_id(doc_id_or_url)
    doc = _docs_service().documents().get(documentId=doc_id).execute()
    return {
        "document_id": doc["documentId"],
        "title": doc.get("title", ""),
        "text": _extract_plain_text(doc.get("body", {})),
    }


def create_document(title: str, body_text: Optional[str] = None) -> dict:
    """
    Create a new Google Doc, optionally inserting initial text.

    Args:
        title: Document title.
        body_text: Optional text to insert into the new document.

    Returns:
        dict with keys: document_id, title, url
    """
    service = _docs_service()
    doc = service.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    if body_text:
        service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": 1}, "text": body_text}}
                ]
            },
        ).execute()

    return {
        "document_id": doc_id,
        "title": title,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit",
    }


def append_text(doc_id_or_url: str, text: str) -> dict:
    """
    Append text to the end of a Google Doc.

    Args:
        doc_id_or_url: Google Docs document ID or full URL.
        text: Text to append.

    Returns:
        dict with keys: document_id, status
    """
    doc_id = _extract_doc_id(doc_id_or_url)
    service = _docs_service()

    doc = service.documents().get(documentId=doc_id).execute()
    body = doc.get("body", {})
    content = body.get("content", [])
    end_index = content[-1]["endIndex"] - 1 if content else 1

    service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {"insertText": {"location": {"index": end_index}, "text": text}}
            ]
        },
    ).execute()

    return {"document_id": doc_id, "status": "ok"}


def replace_text(doc_id_or_url: str, old: str, new: str) -> dict:
    """
    Replace all occurrences of a string in a Google Doc.

    Args:
        doc_id_or_url: Google Docs document ID or full URL.
        old: Text to find (case-sensitive).
        new: Replacement text.

    Returns:
        dict with keys: document_id, occurrences_replaced
    """
    doc_id = _extract_doc_id(doc_id_or_url)
    result = (
        _docs_service()
        .documents()
        .batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "replaceAllText": {
                            "containsText": {"text": old, "matchCase": True},
                            "replaceText": new,
                        }
                    }
                ]
            },
        )
        .execute()
    )
    count = result.get("replies", [{}])[0].get("replaceAllText", {}).get(
        "occurrencesChanged", 0
    )
    return {"document_id": doc_id, "occurrences_replaced": count}


def insert_text(doc_id_or_url: str, text: str, index: int = 1) -> dict:
    """
    Insert text at a specific index in a Google Doc.

    Args:
        doc_id_or_url: Google Docs document ID or full URL.
        text: Text to insert.
        index: Character index to insert at (1 = beginning of body).

    Returns:
        dict with keys: document_id, status
    """
    doc_id = _extract_doc_id(doc_id_or_url)
    _docs_service().documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {"insertText": {"location": {"index": index}, "text": text}}
            ]
        },
    ).execute()
    return {"document_id": doc_id, "status": "ok"}


def batch_update(doc_id_or_url: str, requests: list[dict]) -> dict:
    """
    Send a raw batchUpdate to a Google Doc for advanced edits.

    Args:
        doc_id_or_url: Google Docs document ID or full URL.
        requests: List of Google Docs API request objects.

    Returns:
        dict with keys: document_id, replies
    """
    doc_id = _extract_doc_id(doc_id_or_url)
    result = (
        _docs_service()
        .documents()
        .batchUpdate(documentId=doc_id, body={"requests": requests})
        .execute()
    )
    return {"document_id": doc_id, "replies": result.get("replies", [])}
