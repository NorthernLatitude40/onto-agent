from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, func, SmallInteger, Integer, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship

# Import from the same base as VanModel to ensure consistency
from src.model.van_vehicle_model import Base  # Change this to match VanModel's base


class PricingInventoryModel(Base):
    __tablename__ = "pricing_inventory"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("van_models.id"), nullable=True)
    price_nzd = Column(Numeric(10, 2), nullable=True)
    is_available = Column(Boolean, default=True)
    pickup_location = Column(String(100), nullable=True)
    return_location = Column(String(100), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Use string reference for lazy loading and add backref for bidirectional relationship
    van_model = relationship("VanModel", backref="pricing_inventory")