import time
import random
from datetime import datetime

def generate_sn(prefix: str = "SN") -> str:
    """
    生成高併發下不重複的序列號/訂單號
    格式：[前綴][年月日時分秒][微秒後3位][3位隨機數]
    範例：SN20260819021530123888
    """
    now = datetime.now()
    time_str = now.strftime("%Y%m%d%H%M%S")
    microsec = f"{now.microsecond // 1000:03d}"  # 毫秒部分
    rand_num = f"{random.randint(100, 999)}"      # 隨機數
    
    return f"{prefix}{time_str}{microsec}{rand_num}"