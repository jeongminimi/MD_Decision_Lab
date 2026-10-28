from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...database import Base


class SavedContentDraft(Base):
    """Local persistence owned by the short-form module; no product table reference."""

    __tablename__ = "shortform_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(160))
    brief: Mapped[dict] = mapped_column(JSON)
    hook: Mapped[str] = mapped_column(Text)
    script_beats: Mapped[list[str]] = mapped_column(JSON)
    caption: Mapped[str] = mapped_column(Text)
    call_to_action: Mapped[str] = mapped_column(Text)
    review_note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
