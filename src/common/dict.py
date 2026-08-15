from enum import Enum


class ShopRole(str, Enum):
    """店铺/租户级角色"""
    OWNER = "owner"        # 店主/Boss
    ADMIN = "admin"        # 超级管理员
    MANAGER = "manager"    # 店长
    STAFF = "staff"        # 普通店员

    @property
    def label(self) -> str:
        mapping = {
            ShopRole.OWNER: "Boss",
            ShopRole.ADMIN: "超级管理员",
            ShopRole.MANAGER: "店长",
            ShopRole.STAFF: "店员",
        }
        return mapping.get(self, "店员")