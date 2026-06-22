"""Configure edgartools SEC identity from SEC_USER_AGENT."""

from __future__ import annotations

import os

_identity_configured = False


def ensure_edgar_identity() -> None:
    """Set EDGAR identity once per process (SEC compliance)."""
    global _identity_configured
    if _identity_configured:
        return
    identity = (
        os.getenv("SEC_USER_AGENT", "").strip()
        or os.getenv("EDGAR_IDENTITY", "").strip()
        or "FinancialModelBuilder contact@example.com"
    )
    from edgar import set_identity

    set_identity(identity)
    _identity_configured = True
