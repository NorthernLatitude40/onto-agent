from enum import Enum

# ==============================================================================
# 1. 角色 Enum 定义
# ==============================================================================
class SystemRole(str, Enum):
    """系统级角色"""
    ADMIN = "admin"
    CUSTOMER = "customer"
    MERCHANT = "merchant"


class ShopRole(str, Enum):
    """店铺/租户级角色"""
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"

    @property
    def label(self) -> str:
        mapping = {
            ShopRole.MANAGER: "店長",
            ShopRole.STAFF: "店員",
            ShopRole.OWNER: "Boss",
        }
        return mapping.get(self, "Boss")