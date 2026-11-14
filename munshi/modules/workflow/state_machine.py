"""DRAFT_AI -> NEEDS_REVIEW -> IN_REVIEW -> CHANGES_REQUESTED | APPROVED -> LOCKED -> ANCHORED."""
from __future__ import annotations

from core.errors import InvalidTransition

STATES = ("DRAFT_AI", "NEEDS_REVIEW", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED", "LOCKED", "ANCHORED")

TRANSITIONS: dict[str, set[str]] = {
    "DRAFT_AI": {"NEEDS_REVIEW", "IN_REVIEW"},
    "NEEDS_REVIEW": {"IN_REVIEW"},
    "IN_REVIEW": {"CHANGES_REQUESTED", "APPROVED"},
    "CHANGES_REQUESTED": {"IN_REVIEW"},
    "APPROVED": {"LOCKED", "ANCHORED"},
    "LOCKED": {"ANCHORED"},
    "ANCHORED": set(),
}


def can(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def transition(src: str, dst: str) -> str:
    if not can(src, dst):
        raise InvalidTransition(f"Cannot move from {src} to {dst}")
    return dst
