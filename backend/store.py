"""Session-scoped JSON store — one folder per anonymous user."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"

SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))


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


def find_file_by_dedup_key(session_id: str, dedup_key: str) -> dict | None:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        return None
    for entry in _load_file_entries(session_dir):
        if entry.get("dedup_key") == dedup_key:
            return entry
    return None


def save_file_entry(session_id: str, entry: dict) -> dict:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    files_dir = session_dir / "files"
    files_dir.mkdir(exist_ok=True)
    file_id = entry.get("id") or str(uuid.uuid4())
    record = {**entry, "id": file_id}
    if "created_at" not in record:
        record["created_at"] = _utc_now()
    (files_dir / f"{file_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return record


def _workspace_updated_at(models: list[dict], files: list[dict]) -> str | None:
    timestamps = [
        *(m.get("created_at") for m in models if m.get("created_at")),
        *(f.get("created_at") for f in files if f.get("created_at")),
    ]
    return max(timestamps) if timestamps else None


def _session_created_at(session_dir: Path) -> datetime | None:
    meta_path = session_dir / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        raw = meta.get("created_at")
        if not raw:
            return None
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def cleanup_expired_sessions() -> int:
    """Delete session folders older than SESSION_TTL_SECONDS. Returns count removed."""
    if not SESSIONS_DIR.exists():
        return 0
    now = datetime.now(timezone.utc)
    removed = 0
    for path in SESSIONS_DIR.iterdir():
        if not path.is_dir():
            continue
        created = _session_created_at(path)
        if created is None:
            continue
        age_seconds = (now - created).total_seconds()
        if age_seconds > SESSION_TTL_SECONDS:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def load_workspace(session_id: str) -> dict | None:
    if not session_exists(session_id):
        return None

    session_dir = _session_dir(session_id)
    _migrate_legacy_model(session_dir)
    models = _load_model_entries(session_dir)
    files = _load_file_entries(session_dir)
    updated_at = _workspace_updated_at(models, files)
    return {
        "session_id": session_id,
        "updated_at": updated_at,
        "models": models,
        "files": files,
    }


# --- DCF input bundle (server-side; host records only user-stated values) ---

REQUIRED_DCF_FIELDS = [
    "base_revenue",
    "revenue_growth",
    "ebitda_margin",
    "tax_rate",
    "capex_pct",
    "nwc_pct",
    "wacc",
    "terminal_growth",
    "projection_years",
]

OPTIONAL_DCF_FIELDS = ["net_debt", "shares_outstanding", "company_name"]

ALL_DCF_FIELDS = REQUIRED_DCF_FIELDS + OPTIONAL_DCF_FIELDS


def _inputs_path(session_id: str) -> Path:
    return _session_dir(session_id) / "inputs.json"


def load_input_bundle(session_id: str) -> dict:
    path = _inputs_path(session_id)
    if not path.exists():
        return {"values": {}, "updated_at": None}
    return json.loads(path.read_text(encoding="utf-8"))


def merge_model_inputs(session_id: str, values: dict) -> dict:
    """Merge user-stated values. Ignores unknown keys."""
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    bundle = load_input_bundle(session_id)
    current = dict(bundle.get("values") or {})
    for key, val in values.items():
        if key in ALL_DCF_FIELDS and val is not None:
            current[key] = val

    record = {"values": current, "updated_at": _utc_now()}
    _inputs_path(session_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return summarize_input_bundle(session_id)


def summarize_input_bundle(session_id: str) -> dict:
    bundle = load_input_bundle(session_id)
    values = bundle.get("values") or {}
    missing = [f for f in REQUIRED_DCF_FIELDS if f not in values]
    return {
        "session_id": session_id,
        "filled": {k: values[k] for k in ALL_DCF_FIELDS if k in values},
        "missing_required": missing,
        "ready": len(missing) == 0,
        "updated_at": bundle.get("updated_at"),
    }


def build_dcf_inputs_from_bundle(session_id: str) -> DcfInputs:
    summary = summarize_input_bundle(session_id)
    if not summary["ready"]:
        missing = ", ".join(summary["missing_required"])
        raise ValueError(f"Missing required inputs: {missing}")

    from engine.dcf import DcfInputs

    values = summary["filled"]
    return DcfInputs(
        base_revenue=values["base_revenue"],
        revenue_growth=values["revenue_growth"],
        ebitda_margin=values["ebitda_margin"],
        tax_rate=values["tax_rate"],
        capex_pct=values["capex_pct"],
        nwc_pct=values["nwc_pct"],
        wacc=values["wacc"],
        terminal_growth=values["terminal_growth"],
        projection_years=values["projection_years"],
        net_debt=values.get("net_debt"),
        shares_outstanding=values.get("shares_outstanding"),
    )


def company_name_from_bundle(session_id: str) -> str | None:
    values = load_input_bundle(session_id).get("values") or {}
    name = values.get("company_name")
    return str(name).strip() if name else None
