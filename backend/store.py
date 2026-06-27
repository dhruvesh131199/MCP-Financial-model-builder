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
    (session_dir / "inputs").mkdir(exist_ok=True)
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


def get_model_entry(session_id: str, model_id: str) -> dict | None:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        return None
    path = session_dir / "models" / f"{model_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def update_model_entry(session_id: str, model_id: str, *, data: dict | None = None) -> dict:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")
    path = session_dir / "models" / f"{model_id}.json"
    if not path.exists():
        raise KeyError("Model not found")
    entry = json.loads(path.read_text(encoding="utf-8"))
    if data is not None:
        entry["data"] = data
    entry["updated_at"] = _utc_now()
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def save_dcf_draft_model(session_id: str, payload: dict) -> dict:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    models_dir = session_dir / "models"
    models_dir.mkdir(exist_ok=True)
    _migrate_legacy_model(session_dir)

    existing_names = [m["name"] for m in _load_model_entries(session_dir)]
    company = payload.get("company_name")
    years = int(payload.get("projection_years") or 5)
    model_id = str(uuid.uuid4())
    entry = {
        "id": model_id,
        "name": _build_dcf_name(company, years, existing_names),
        "type": "dcf_draft",
        "created_at": _utc_now(),
        "data": payload,
    }
    (models_dir / f"{model_id}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def find_dcf_computed_for_draft(session_id: str, draft_id: str) -> dict | None:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        return None
    for entry in _load_model_entries(session_dir):
        if entry.get("type") != "dcf":
            continue
        if entry.get("draft_id") == draft_id:
            return entry
        data = entry.get("data") or {}
        if data.get("draft_id") == draft_id:
            return entry
    return None


def upsert_dcf_computed_from_draft(
    session_id: str,
    draft_id: str,
    draft_entry: dict,
    payload: dict,
) -> dict:
    """Create or update the read-only valuation twin for a dcf_draft (one twin per draft)."""
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    models_dir = session_dir / "models"
    models_dir.mkdir(exist_ok=True)

    linked = {**payload, "draft_id": draft_id}
    existing = find_dcf_computed_for_draft(session_id, draft_id)

    if existing:
        model_id = existing["id"]
        entry = {
            **existing,
            "name": draft_entry.get("name", existing.get("name")),
            "type": "dcf",
            "draft_id": draft_id,
            "data": linked,
            "updated_at": _utc_now(),
        }
    else:
        model_id = str(uuid.uuid4())
        entry = {
            "id": model_id,
            "name": draft_entry.get("name", "dcf"),
            "type": "dcf",
            "draft_id": draft_id,
            "created_at": _utc_now(),
            "data": linked,
        }

    (models_dir / f"{model_id}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def ticker_financials_dedup_key(ticker: str) -> str:
    return f"{ticker.upper()}|financials"


def find_financials_file_for_ticker(session_id: str, ticker: str) -> dict | None:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        return None

    sym = ticker.upper()
    dedup = ticker_financials_dedup_key(sym)
    for entry in _load_file_entries(session_dir):
        if entry.get("dedup_key") == dedup:
            return entry
    for entry in _load_file_entries(session_dir):
        if entry.get("type") != "financials":
            continue
        data = entry.get("data") or {}
        if str(data.get("ticker", "")).upper() == sym:
            return entry
    return None


def upsert_ticker_financials_file(
    session_id: str,
    ticker: str,
    financials,
) -> dict:
    """Create or update the single Files entry for a ticker."""
    sym = ticker.upper()
    dedup_key = ticker_financials_dedup_key(sym)
    payload = financials.model_dump() if hasattr(financials, "model_dump") else financials
    existing = find_financials_file_for_ticker(session_id, sym)
    if existing:
        return update_file_entry(
            session_id,
            existing["id"],
            {
                "name": sym,
                "type": "financials",
                "dedup_key": dedup_key,
                "data": payload,
            },
        )
    return save_file_entry(
        session_id,
        {
            "name": sym,
            "type": "financials",
            "dedup_key": dedup_key,
            "data": payload,
        },
    )


def find_detailed_analysis_by_ticker(session_id: str, ticker: str) -> dict | None:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        return None

    sym = ticker.upper()
    for entry in _load_model_entries(session_dir):
        if entry.get("type") != "detailed_analysis":
            continue
        data = entry.get("data") or {}
        if str(data.get("ticker", "")).upper() == sym:
            return entry
    return None


def save_detailed_analysis_model(session_id: str, payload: dict) -> dict:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    models_dir = session_dir / "models"
    models_dir.mkdir(exist_ok=True)
    _migrate_legacy_model(session_dir)

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    ticker = str(data.get("ticker") or "NONE").upper()
    existing = find_detailed_analysis_by_ticker(session_id, ticker)

    if existing:
        model_id = existing["id"]
        entry = {
            **existing,
            "name": ticker,
            "type": "detailed_analysis",
            "data": data,
            "source": payload.get("source") or existing.get("source"),
            "updated_at": _utc_now(),
        }
        (models_dir / f"{model_id}.json").write_text(
            json.dumps(entry, indent=2), encoding="utf-8"
        )
        return entry

    model_id = str(uuid.uuid4())
    entry = {
        "id": model_id,
        "name": ticker,
        "type": "detailed_analysis",
        "created_at": _utc_now(),
        "data": data,
        "source": payload.get("source"),
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


def update_file_entry(session_id: str, file_id: str, updates: dict) -> dict:
    """Update an existing file entry in place (same id, refreshes data)."""
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    path = session_dir / "files" / f"{file_id}.json"
    if not path.exists():
        raise KeyError("File not found")

    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(updates)
    record["id"] = file_id
    record["updated_at"] = _utc_now()
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def _entry_timestamp(entry: dict) -> str | None:
    """Latest activity time for a model or file entry."""
    candidates = [entry.get("updated_at"), entry.get("created_at")]
    valid = [t for t in candidates if t]
    return max(valid) if valid else None


def _statements_inputs_path(session_id: str) -> Path:
    session_dir = _session_dir(session_id)
    inputs_dir = session_dir / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    return inputs_dir / "statements.json"


def load_statements_index_raw(session_id: str) -> dict | None:
    path = _statements_inputs_path(session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_statements_index_raw(session_id: str, payload: dict) -> None:
    path = _statements_inputs_path(session_id)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _workspace_updated_at(
    models: list[dict],
    files: list[dict],
    *,
    extra_timestamps: list[str | None] | None = None,
) -> str | None:
    timestamps = [
        *(_entry_timestamp(m) for m in models),
        *(_entry_timestamp(f) for f in files),
        *(t for t in (extra_timestamps or []) if t),
    ]
    timestamps = [t for t in timestamps if t]
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
    stmt_path = session_dir / "inputs" / "statements.json"
    stmt_mtime: str | None = None
    if stmt_path.exists():
        stmt_mtime = datetime.fromtimestamp(
            stmt_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    updated_at = _workspace_updated_at(models, files, extra_timestamps=[stmt_mtime])
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

MAX_COMPARATIVE_PEERS = 10


def _inputs_dir(session_id: str) -> Path:
    return _session_dir(session_id) / "inputs"


def _migrate_legacy_inputs(session_dir: Path) -> None:
    """Move legacy inputs.json at session root into inputs/dcf.json."""
    legacy = session_dir / "inputs.json"
    if not legacy.exists():
        return
    inputs_dir = session_dir / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    target = inputs_dir / "dcf.json"
    if not target.exists():
        target.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
    legacy.unlink(missing_ok=True)


def _dcf_inputs_path(session_id: str) -> Path:
    session_dir = _session_dir(session_id)
    _migrate_legacy_inputs(session_dir)
    inputs_dir = session_dir / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    return inputs_dir / "dcf.json"


def _comparative_inputs_path(session_id: str) -> Path:
    session_dir = _session_dir(session_id)
    _migrate_legacy_inputs(session_dir)
    inputs_dir = session_dir / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    return inputs_dir / "comparative.json"


def load_input_bundle(session_id: str) -> dict:
    path = _dcf_inputs_path(session_id)
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
    _dcf_inputs_path(session_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
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


# --- Comparative input bundle ---


def _empty_comparative_bundle() -> dict:
    return {
        "model_type": "comparative",
        "fiscal_year": None,
        "target": None,
        "peers": [],
        "updated_at": None,
    }


def load_comparative_bundle(session_id: str) -> dict:
    path = _comparative_inputs_path(session_id)
    if not path.exists():
        return _empty_comparative_bundle()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {**_empty_comparative_bundle(), **data}


def _save_comparative_bundle(session_id: str, bundle: dict) -> None:
    record = {**bundle, "updated_at": _utc_now()}
    _comparative_inputs_path(session_id).write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )


def get_file_entry(session_id: str, file_id: str) -> dict | None:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        return None
    for entry in _load_file_entries(session_dir):
        if entry.get("id") == file_id:
            return entry
    return None


def latest_annual_fiscal_year(financials_data: dict) -> int | None:
    """Latest FY with annual income data; prefer 10-K when tagged."""
    statements = financials_data.get("statements") or {}
    income = statements.get("income") or {}
    annual = income.get("annual") or []
    if not annual:
        return None
    ten_k = [p for p in annual if p.get("form") == "10-K"]
    periods = ten_k if ten_k else annual
    return max(int(p["fiscal_year"]) for p in periods)


def has_annual_fiscal_year(financials_data: dict, fiscal_year: int) -> bool:
    statements = financials_data.get("statements") or {}
    income = statements.get("income") or {}
    for period in income.get("annual") or []:
        if int(period.get("fiscal_year", 0)) == fiscal_year:
            return True
    return False


def _normalize_company_slot(raw: dict | None) -> dict | None:
    if not raw:
        return None
    slot: dict = {}
    if raw.get("company_name"):
        slot["company_name"] = str(raw["company_name"]).strip()
    if raw.get("ticker"):
        slot["ticker"] = str(raw["ticker"]).strip().upper()
    if raw.get("file_id"):
        slot["file_id"] = str(raw["file_id"]).strip()
    return slot or None


def _merge_company_slot(existing: dict | None, update: dict) -> dict:
    base = dict(existing or {})
    merged = _normalize_company_slot({**base, **update})
    return merged or {}


def merge_comparative_inputs(session_id: str, values: dict) -> dict:
    """Merge comparative target/peers/fiscal_year. Partial updates supported."""
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    bundle = load_comparative_bundle(session_id)

    if "fiscal_year" in values:
        fy = values["fiscal_year"]
        bundle["fiscal_year"] = int(fy) if fy is not None else None

    if values.get("target") is not None:
        bundle["target"] = _merge_company_slot(bundle.get("target"), values["target"])

    if values.get("peers") is not None:
        peers_in = values["peers"]
        if not isinstance(peers_in, list):
            raise ValueError("peers must be a list")
        if len(peers_in) > MAX_COMPARATIVE_PEERS:
            raise ValueError(f"At most {MAX_COMPARATIVE_PEERS} peers allowed")
        bundle["peers"] = [
            slot
            for slot in (_normalize_company_slot(p) for p in peers_in)
            if slot is not None
        ]

    if values.get("link"):
        link = values["link"]
        ticker = str(link.get("ticker", "")).strip().upper()
        file_id = link.get("file_id")
        if not ticker or not file_id:
            raise ValueError("link requires ticker and file_id")
        name = link.get("company_name")
        updated = False
        target = bundle.get("target")
        if target and target.get("ticker") == ticker:
            bundle["target"] = _merge_company_slot(
                target, {"file_id": file_id, **({"company_name": name} if name else {})}
            )
            updated = True
        for i, peer in enumerate(bundle.get("peers") or []):
            if peer.get("ticker") == ticker:
                bundle["peers"][i] = _merge_company_slot(
                    peer, {"file_id": file_id, **({"company_name": name} if name else {})}
                )
                updated = True
        if not updated:
            raise ValueError(f"No company slot found for ticker {ticker}")

    sync_comparative_file_links(session_id, bundle)
    _save_comparative_bundle(session_id, bundle)
    return summarize_comparative_bundle(session_id)


def sync_comparative_file_links(session_id: str, bundle: dict | None = None) -> dict:
    """Attach ticker Files entries to comparative slots when file_id is missing."""
    if bundle is None:
        bundle = load_comparative_bundle(session_id)

    target = bundle.get("target")
    if target and target.get("ticker") and not target.get("file_id"):
        entry = find_financials_file_for_ticker(session_id, target["ticker"])
        if entry:
            bundle["target"] = _merge_company_slot(target, {"file_id": entry["id"]})

    peers = list(bundle.get("peers") or [])
    for i, peer in enumerate(peers):
        if peer.get("ticker") and not peer.get("file_id"):
            entry = find_financials_file_for_ticker(session_id, peer["ticker"])
            if entry:
                peers[i] = _merge_company_slot(peer, {"file_id": entry["id"]})
    bundle["peers"] = peers
    return bundle


def apply_comparative_file_links(session_id: str) -> None:
    """Load bundle, link ticker Files entries, persist."""
    bundle = load_comparative_bundle(session_id)
    bundle = sync_comparative_file_links(session_id, bundle)
    _save_comparative_bundle(session_id, bundle)


def resolve_comparative_fiscal_year(
    session_id: str, bundle: dict, companies: list[dict]
) -> tuple[int | None, str | None]:
    """Pick fiscal year: user override or min of each company's latest annual FY."""
    explicit = bundle.get("fiscal_year")
    if explicit is not None:
        fy = int(explicit)
        for company in companies:
            file_id = company.get("file_id")
            if not file_id:
                continue
            entry = get_file_entry(session_id, file_id)
            if not entry or not has_annual_fiscal_year(entry.get("data") or {}, fy):
                return None, f"FY{fy} not available for {company.get('ticker', '?')}"
        return fy, f"Using user-selected FY{fy}."

    per_company: list[tuple[str, int]] = []
    for company in companies:
        file_id = company.get("file_id")
        if not file_id:
            return None, None
        entry = get_file_entry(session_id, file_id)
        if not entry:
            return None, None
        latest = latest_annual_fiscal_year(entry.get("data") or {})
        if latest is None:
            return None, None
        per_company.append((str(company.get("ticker", "?")), latest))

    if not per_company:
        return None, None

    target_ticker = str(
        next((c.get("ticker") for c in companies if c.get("role") == "target"), per_company[0][0])
    )
    target_fy = next((fy for t, fy in per_company if t == target_ticker), per_company[0][1])
    if len({fy for _, fy in per_company}) == 1:
        note = f"Using FY{target_fy} for all companies."
    else:
        parts = ", ".join(f"{t} FY{fy}" for t, fy in per_company)
        note = f"Each company's latest annual FY: {parts}."
    return target_fy, note


def summarize_comparative_bundle(session_id: str) -> dict:
    bundle = load_comparative_bundle(session_id)
    missing: list[str] = []
    target = bundle.get("target")

    if not target or not target.get("ticker"):
        missing.append("target.ticker")
    peers = bundle.get("peers") or []
    if len(peers) < 1:
        missing.append("peers (need 1–10)")
    if len(peers) > MAX_COMPARATIVE_PEERS:
        missing.append(f"peers (max {MAX_COMPARATIVE_PEERS})")

    companies: list[dict] = []
    if target and target.get("ticker"):
        companies.append({**target, "role": "target"})
    for i, peer in enumerate(peers):
        if not peer.get("ticker"):
            missing.append(f"peers[{i}].ticker")
        else:
            companies.append({**peer, "role": "peer"})

    for company in companies:
        ticker = company.get("ticker", "?")
        if not company.get("file_id"):
            missing.append(f"{ticker}.file_id")
            continue
        entry = get_file_entry(session_id, company["file_id"])
        if not entry:
            missing.append(f"{ticker}.file_id (not found)")

    fiscal_year_used: int | None = None
    fiscal_year_note: str | None = None
    if not any(m.endswith(".file_id") or "file_id" in m for m in missing):
        ready_files = all(
            company.get("file_id") and get_file_entry(session_id, company["file_id"])
            for company in companies
        )
        if ready_files and companies:
            fiscal_year_used, fiscal_year_note = resolve_comparative_fiscal_year(
                session_id, bundle, companies
            )
            if fiscal_year_used is None and bundle.get("fiscal_year") is not None:
                missing.append("fiscal_year (not available for all companies)")

    ready = len(missing) == 0 and fiscal_year_used is not None

    next_step = "Call run_comparative_analysis()."
    if not target or not target.get("ticker"):
        next_step = "Set target company (ticker or name) via set_comparative_inputs."
    elif len(peers) < 1:
        next_step = "Add 1–10 peer companies via set_comparative_inputs."
    elif any(not c.get("file_id") for c in companies):
        next_step = (
            "Ensure SEC Files exist for each ticker (fetch_sec_financials) or call "
            "run_comparative_analysis to auto-fetch and link."
        )
    elif fiscal_year_used is None:
        next_step = "Ensure SEC files include annual data for the chosen fiscal year."
    elif not ready:
        next_step = f"Still missing: {', '.join(missing)}"

    return {
        "session_id": session_id,
        "model_type": "comparative",
        "target": target,
        "peers": peers,
        "fiscal_year": bundle.get("fiscal_year"),
        "fiscal_year_used": fiscal_year_used,
        "fiscal_year_note": fiscal_year_note,
        "missing": missing,
        "ready": ready,
        "updated_at": bundle.get("updated_at"),
        "next_step": next_step,
    }


def _build_comparative_name(target_ticker: str | None, peer_count: int, existing: list[str]) -> str:
    slug = _slugify(target_ticker or "none")
    base = f"{slug}_comps_{peer_count}p"
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def save_comparative_model(session_id: str, payload: dict) -> dict:
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    models_dir = session_dir / "models"
    models_dir.mkdir(exist_ok=True)
    _migrate_legacy_model(session_dir)

    existing_names = [m["name"] for m in _load_model_entries(session_dir)]
    target_ticker = (payload.get("target") or {}).get("ticker")
    peer_count = len(payload.get("peers") or [])
    model_id = str(uuid.uuid4())
    entry = {
        "id": model_id,
        "name": _build_comparative_name(target_ticker, peer_count, existing_names),
        "type": "comparative",
        "created_at": _utc_now(),
        "data": payload,
    }
    (models_dir / f"{model_id}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry
