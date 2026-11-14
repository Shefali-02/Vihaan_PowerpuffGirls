"""Trust tables: append-only audit chain, Merkle leaves/batches, published reports, mock anchors."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin
from core.errors import ImmutableRecord


class AuditEvent(Base, IdMixin, WorkspaceMixin):
    __tablename__ = "audit_events"
    __table_args__ = (UniqueConstraint("workspace_id", "seq"),)
    seq: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    object_type: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[str] = mapped_column(String(40))  # ISO string: exact bytes are hashed
    payload: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=False)
    salt: Mapped[str | None] = mapped_column(String(32), nullable=True)  # off-chain only
    leaf_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


@event.listens_for(AuditEvent, "before_update")
def _no_update(mapper, connection, target):
    raise ImmutableRecord("Audit events are append-only")


@event.listens_for(AuditEvent, "before_delete")
def _no_delete(mapper, connection, target):
    raise ImmutableRecord("Audit events are append-only")


class ChainHead(Base):
    __tablename__ = "audit_chain_heads"
    workspace_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    head_hash: Mapped[str] = mapped_column(String(64))


class MerkleBatch(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "merkle_batches"
    __table_args__ = (UniqueConstraint("workspace_id", "batch_seq"),)
    batch_seq: Mapped[int] = mapped_column(Integer)
    root: Mapped[str] = mapped_column(String(64))
    leaf_count: Mapped[int] = mapped_column(Integer)
    from_seq: Mapped[int] = mapped_column(Integer)
    to_seq: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(40))
    anchor_mode: Mapped[str] = mapped_column(String(10))  # HARDHAT | MOCK
    chain_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_address: Mapped[str | None] = mapped_column(String(42), nullable=True)
    tx_hash: Mapped[str] = mapped_column(String(66))
    block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MerkleLeaf(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "merkle_leaves"
    __table_args__ = (UniqueConstraint("workspace_id", "audit_seq"),)
    audit_seq: Mapped[int] = mapped_column(Integer, index=True)
    leaf_hash: Mapped[str] = mapped_column(String(64))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("merkle_batches.id"), nullable=True, index=True)
    leaf_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proof: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Report(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    __tablename__ = "reports"
    period_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="investor_pack")
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(200))
    pdf: Mapped[bytes] = mapped_column(LargeBinary)
    pack_json: Mapped[dict] = mapped_column(JSON)
    audit_seq: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(36))


class MockAnchor(Base, IdMixin, WorkspaceMixin, TimestampMixin):
    """Stand-in for the chain when ANCHOR_MODE=mock or the node is unreachable. Labelled MOCK everywhere."""

    __tablename__ = "mock_anchors"
    __table_args__ = (UniqueConstraint("ws_chain_id", "seq"),)
    ws_chain_id: Mapped[str] = mapped_column(String(64))
    seq: Mapped[int] = mapped_column(Integer)
    root: Mapped[str] = mapped_column(String(64))
    tx_hash: Mapped[str] = mapped_column(String(66))
    block_number: Mapped[int] = mapped_column(Integer)
