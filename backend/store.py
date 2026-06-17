"""Session-scoped JSON store — one folder per anonymous user."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"

SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_session_id(session_id: str) -> str:
    sid = session_id.strip()
    if not SESSION_ID_PATTERN.match(sid):
        raise ValueError("Invalid session_id")
    return sid


def _session_dir(session_id: str) -> Path:
    return SESSIONS_DIR / _validate_session_id(session_id)


def session_exists(session_id: str) -> bool:
    try:
        return _session_dir(session_id).is_dir()
    except ValueError:
        return False


def create_session() -> str:
    """Create a new anonymous session folder. No login required."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=False)
    (session_dir / "models").mkdir(exist_ok=True)
    (session_dir / "files").mkdir(exist_ok=True)
    meta = {"session_id": session_id, "created_at": _utc_now()}
    (session_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return session_id


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower().strip())
    return slug.strip("_") or "none"


def _build_dcf_name(company_name: str | None, projection_years: int, existing: list[str]) -> str:
    slug = _slugify(company_name) if company_name and company_name.strip() else "none"
    base = f"{slug}_dcf_{projection_years}"
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def _migrate_legacy_model(session_dir: Path) -> None:
    """Move old single model.json into models/ folder."""
    legacy = session_dir / "model.json"
    if not legacy.exists():
        return
    models_dir = session_dir / "models"
    models_dir.mkdir(exist_ok=True)
    raw = json.loads(legacy.read_text(encoding="utf-8"))
    payload = raw.get("model") or raw
    if not payload:
        legacy.unlink(missing_ok=True)
        return
    model_id = str(uuid.uuid4())
    company = payload.get("company_name")
    years = payload.get("inputs", {}).get("projection_years", 5)
    entry = {
        "id": model_id,
        "name": _build_dcf_name(company, years, []),
        "type": "dcf",
        "created_at": raw.get("updated_at") or _utc_now(),
        "data": payload,
    }
    (models_dir / f"{model_id}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    legacy.unlink(missing_ok=True)


def save_dcf_model(session_id: str, payload: dict) -> dict:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    models_dir = session_dir / "models"
    models_dir.mkdir(exist_ok=True)
    _migrate_legacy_model(session_dir)

    existing_names = [m["name"] for m in _load_model_entries(session_dir)]
    company = payload.get("company_name")
    years = payload.get("inputs", {}).get("projection_years", 5)
    model_id = str(uuid.uuid4())
    entry = {
        "id": model_id,
        "name": _build_dcf_name(company, years, existing_names),
        "type": "dcf",
        "created_at": _utc_now(),
        "data": payload,
    }
    (models_dir / f"{model_id}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def _load_model_entries(session_dir: Path) -> list[dict]:
    models_dir = session_dir / "models"
    if not models_dir.exists():
        return []
    entries: list[dict] = []
    for path in models_dir.glob("*.json"):
        entries.append(json.loads(path.read_text(encoding="utf-8")))
    entries.sort(key=lambda e: e.get("created_at", ""))
    return entries


def _load_file_entries(session_dir: Path) -> list[dict]:
    files_dir = session_dir / "files"
    if not files_dir.exists():
        return []
    entries: list[dict] = []
    for path in files_dir.glob("*.json"):
        entries.append(json.loads(path.read_text(encoding="utf-8")))
    entries.sort(key=lambda e: e.get("created_at", ""))
    return entries


def load_workspace(session_id: str) -> dict | None:
    if not session_exists(session_id):
        return None

    session_dir = _session_dir(session_id)
    _migrate_legacy_model(session_dir)
    models = _load_model_entries(session_dir)
    files = _load_file_entries(session_dir)
    updated_at = None
    if models:
        updated_at = models[-1].get("created_at")
    return {
        "session_id": session_id,
        "updated_at": updated_at,
        "models": models,
        "files": files,
    }
