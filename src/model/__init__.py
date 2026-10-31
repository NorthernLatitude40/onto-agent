# Import all models to ensure they are registered with SQLAlchemy
from .van_vehicle_model import VanModel, Base as VanBase
from .pricing_inventory_model import PricingInventoryModel

# Ensure both models use the same base for consistency
__all__ = ['VanModel', 'PricingInventoryModel', 'VanBase']