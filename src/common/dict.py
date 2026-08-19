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

class InboundStatusEnum(IntEnum):
    PENDING = 1      # 未完成入庫 / 待入庫
    COMPLETED = 2    # 已完成入庫
    CANCEL = 3    # 已取消
    RETURNED = 0  # 若未來有退貨或取消可彈性擴充

class InventoryStatusEnum(IntEnum):
    IN_STOCK = 1     # 在庫 / 在售
    SOLD = 2         # 已售出
    LOCKED = 3       # 鎖定 / 預留 / 維修（例如已被訂購但未出庫）
    RETURNED = 4     # 已退貨/待處理
    SCRAPPED = 5     # 已報廢 / 損壞