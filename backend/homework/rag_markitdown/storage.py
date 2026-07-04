"""Document folder layout for homework ingest."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from store import DATA_DIR, session_exists

OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def allocate_output_dir(
    *,
    session_id: str | None = None,
    ticker: str | None = None,
    homework_output: bool = False,
) -> tuple[str, Path]:
    document_id = str(uuid.uuid4())
    if homework_output or not session_id:
        label = (ticker or "upload").upper()
        out = OUTPUT_ROOT / f"{label}_{_utc_stamp()}"
    else:
        if not session_exists(session_id):
            raise KeyError("Session not found")
        out = DATA_DIR / "sessions" / session_id / "documents" / document_id
    out.mkdir(parents=True, exist_ok=True)
    return document_id, out


def write_meta(out_dir: Path, payload: dict) -> Path:
    path = out_dir / "meta.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_meta(out_dir: Path) -> dict:
    path = out_dir / "meta.json"
    if not path.is_file():
        raise FileNotFoundError(f"meta.json not found in {out_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def find_document_dir(session_id: str, document_id: str) -> Path:
    path = DATA_DIR / "sessions" / session_id / "documents" / document_id
    if not path.is_dir():
        raise FileNotFoundError("Document not found")
    return path


def find_homework_document_by_id(document_id: str) -> Path | None:
    if not OUTPUT_ROOT.is_dir():
        return None
    for meta_path in OUTPUT_ROOT.glob("*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("document_id") == document_id:
            return meta_path.parent
    return None


def ensure_session_document_dir(session_id: str, document_id: str) -> Path | None:
    """Return session document dir, copying from homework lab output if needed."""
    try:
        return find_document_dir(session_id, document_id)
    except FileNotFoundError:
        pass
    hw_dir = find_homework_document_by_id(document_id)
    if hw_dir is None:
        return None
    dest = DATA_DIR / "sessions" / session_id / "documents" / document_id
    dest.mkdir(parents=True, exist_ok=True)
    for item in hw_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)
    return dest


def session_document_has_report(session_id: str, document_id: str) -> bool:
    try:
        out_dir = find_document_dir(session_id, document_id)
    except FileNotFoundError:
        out_dir = ensure_session_document_dir(session_id, document_id)
    if out_dir is None:
        return False
    return (out_dir / "report.html").is_file()
