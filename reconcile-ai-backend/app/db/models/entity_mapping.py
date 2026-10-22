from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EntityMapping(Base):
    __tablename__ = "entity_mappings"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')"),
        UniqueConstraint("owner_user_id", "source_name", name="uq_entity_mappings_owner_source"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="NOW()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="NOW()", onupdate="NOW()")

    owner_user: Mapped["User"] = relationship(
        back_populates="entity_mappings",
        foreign_keys=[owner_user_id],
    )
    approved_by_user: Mapped["User | None"] = relationship(
        back_populates="approved_entity_mappings",
        foreign_keys=[approved_by],
    )
    exceptions: Mapped[list["ExceptionRecord"]] = relationship(back_populates="entity_mapping")
