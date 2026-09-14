"""Fourthwall webhook verification + deduplication (spec C3/C5).

HMAC-SHA256 signature verification against a shared secret.  Event dedup by
event id with a 24-hour TTL (memory-only, no second event store — refinement
rule).  Rejects unverifiable payloads; never trusts the body alone.

Assumed header: ``X-Webhook-Signature`` — hex-encoded HMAC-SHA256 of the raw
request body using ``FOURTHWALL_WEBHOOK_SECRET``.  If Fourthwall's real scheme
differs, the refinement rule requires recording the verified scheme here and in
the spec Decisions before accepting events.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """HMAC-SHA256 verification (constant-time, never raises)."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Deduplication (in-memory, 24-hour TTL)
# ---------------------------------------------------------------------------

_TTL = 86400  # 24 hours in seconds
_seen: dict[str, float] = {}


def reset_dedup() -> None:
    """Clear the dedup store — test-only helper, never called in production."""
    _seen.clear()


def is_duplicate(event_id: str) -> bool:
    """Return True if this event_id was already processed (within TTL)."""
    _evict()
    if event_id in _seen:
        return True
    _seen[event_id] = time.time()
    return False


def _evict() -> None:
    now = time.time()
    expired = [k for k, t in _seen.items() if now - t > _TTL]
    for k in expired:
        del _seen[k]
