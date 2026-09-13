"""Identity endpoint — the Control Panel resolves the current actor/role here."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import Actor, get_current_actor

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me")
def read_me(actor: Actor = Depends(get_current_actor)) -> dict[str, str]:
    return {"user_id": actor.user_id, "email": actor.email, "role": actor.role}
