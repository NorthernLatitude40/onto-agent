from enum import Enum, IntEnum


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

class DeviceTypeEnum(IntEnum):
    NEW = 1        # 新機
    USED = 2       # 二手機
    ACCESSORY = 3  # 配件

class StockStatusEnum(IntEnum):
    """
    設備庫存狀態列舉 (以單台設備/IMEI為粒度)
    """
    RETURNED = 0   # 已退貨 (退回給供應商)
    PENDING = 1    # 待入庫 / 驗收中
    IN_STOCK = 2   # 在庫 / 正常可售
    SOLD = 3       # 已售出
    REPAIRING = 4  # 維修 / 複測中
    SCRAPPED = 5   # 已報廢
    CANCELLED = 6  # 已取消

class PaymentStatusEnum(IntEnum):
    RETURNED = 0   # 已退款
    PAYING = 1    # 待支付
    PAYED = 2   # 支付完成
    CANCELLED = 3       # 已取消
    