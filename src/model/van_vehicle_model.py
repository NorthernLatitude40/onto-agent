from datetime import datetime
from typing import Any, Optional
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
  pass


class VanModel(Base):
  __tablename__ = "van_models"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  model_name: Mapped[str] = mapped_column(String(100), nullable=False)
  berths: Mapped[Optional[int]] = mapped_column(Integer, server_default="2")
  transmission: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
  specs: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
  created_at: Mapped[Optional[datetime]] = mapped_column(
      DateTime(timezone=True), server_default=func.current_timestamp()
  )

  

  def __repr__(self) -> str:
    return (
        f"<VanModel(id={self.id}, model_name='{self.model_name}',"
        f" berths={self.berths})>"
    )