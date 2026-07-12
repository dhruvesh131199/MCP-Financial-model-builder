"""Pin host-authored RAG markdown answers to the dashboard."""

from __future__ import annotations

from store import save_rag_display_model
from services.da_narrative_store import save_da_narrative


def pin_rag_display(
    session_id: str,
    *,
    name: str,
    content: str,
    destination: str | None = None,
    ticker: str | None = None,
    section_key: str | None = None,
) -> dict:
    """Pin markdown to RAG Results (default) or a Detailed Analysis narrative section.

    Use when: host finishes query_rag and wants a durable dashboard reference.
    Logic: destination omit/rag_results → sidebar model; detailed_analysis → session md file.
    Returns: success payload or error dict.
    """
    dest = (destination or "rag_results").strip().lower() or "rag_results"

    if dest in ("rag_results", "rag_result", "results"):
        try:
            entry = save_rag_display_model(session_id, name=name, content_md=content)
        except KeyError:
            return {"error": "session_not_found", "message": "Session not found"}
        except ValueError as exc:
            return {"error": "invalid_input", "message": str(exc)}

        return {
            "success": True,
            "destination": "rag_results",
            "result_id": entry["id"],
            "name": entry["name"],
            "message": (
                f"Pinned '{entry['name']}' to RAG Results. "
                "Open your dashboard → RAG Results sidebar → click the chip to view."
            ),
        }

    if dest == "detailed_analysis":
        if not ticker or not str(ticker).strip():
            return {
                "error": "invalid_input",
                "message": "ticker is required when destination=detailed_analysis",
            }
        if not section_key or not str(section_key).strip():
            return {
                "error": "invalid_input",
                "message": "section_key is required when destination=detailed_analysis",
            }
        try:
            saved = save_da_narrative(
                session_id,
                ticker,
                section_key,
                content,
            )
        except KeyError:
            return {"error": "session_not_found", "message": "Session not found"}
        except ValueError as exc:
            return {"error": "invalid_input", "message": str(exc)}

        title = saved["title"]
        return {
            "success": True,
            "destination": "detailed_analysis",
            "ticker": saved["ticker"],
            "section_key": saved["section_key"],
            "name": name.strip() or title,
            "title": title,
            "message": (
                f"Pinned '{title}' on Detailed Analysis for {saved['ticker']}. "
                "Open Detailed Analysis → scroll to narrative sections."
            ),
        }

    return {
        "error": "invalid_input",
        "message": (
            f"Unknown destination={destination!r}. "
            "Use 'rag_results' (default) or 'detailed_analysis'."
        ),
    }
