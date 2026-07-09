"""Pin host-authored RAG markdown answers to the dashboard."""

from __future__ import annotations

from store import save_rag_display_model


def pin_rag_display(session_id: str, *, name: str, content: str) -> dict:
    """Save a markdown RAG result for sidebar display."""
    try:
        entry = save_rag_display_model(session_id, name=name, content_md=content)
    except KeyError:
        return {"error": "session_not_found", "message": "Session not found"}
    except ValueError as exc:
        return {"error": "invalid_input", "message": str(exc)}

    return {
        "success": True,
        "result_id": entry["id"],
        "name": entry["name"],
        "message": (
            f"Pinned '{entry['name']}' to RAG Results. "
            "Open your dashboard → RAG Results sidebar → click the chip to view."
        ),
    }
