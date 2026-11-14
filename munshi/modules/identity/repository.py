from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.identity.models import Membership, User, Workspace


def user_by_email(s: Session, email: str) -> User | None:
    return s.scalar(select(User).where(User.email == email.lower()))


def user_by_id(s: Session, user_id: str) -> User | None:
    return s.get(User, user_id)


def memberships_for(s: Session, user_id: str) -> list[Membership]:
    return list(s.scalars(select(Membership).where(Membership.user_id == user_id)))


def membership(s: Session, workspace_id: str, user_id: str) -> Membership | None:
    return s.scalar(select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id))


def workspace(s: Session, workspace_id: str) -> Workspace | None:
    return s.get(Workspace, workspace_id)


def all_workspace_ids(s: Session) -> list[str]:
    return list(s.scalars(select(Workspace.id)))
