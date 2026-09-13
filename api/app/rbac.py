"""Server-side role enforcement (spec C2).

Every protected route declares its allowed roles with ``require_role(...)``.
The UI may hide controls cosmetically, but the API is the enforcement point:
no session -> 401, insufficient role -> 403.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from .auth import Actor, get_current_actor


def require_role(*allowed: str) -> Callable[[Actor], Actor]:
    """Build a dependency that only admits callers whose role is in ``allowed``."""
    if not allowed:
        raise ValueError("require_role() needs at least one role")

    def dependency(actor: Actor = Depends(get_current_actor)) -> Actor:
        if actor.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return actor

    return dependency
