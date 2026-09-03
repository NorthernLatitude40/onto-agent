# src/services/discount.py


def calculate_discount(price, discount_rate):
    # 邊界檢查：若 discount_rate 不在 0 到 1 之間，拋出 ValueError
    if not (0 <= discount_rate <= 1):
        raise ValueError('折扣率必須介於 0 與 1 之間')

    # 修正計算邏輯：打折後價格應為 price * (1 - discount_rate)
    return price * (1 - discount_rate)

assert calculate_discount(100, 0.2) == 80
try:
    calculate_discount(100, 1.5)
    assert False, '未成功拋出 ValueError (discount_rate > 1)'
except ValueError as e:
    assert str(e) == '折扣率必須介於 0 與 1 之間'

try:
    calculate_discount(100, -0.1)
    assert False, '未成功拋出 ValueError (discount_rate < 0)'
except ValueError as e:
    assert str(e) == '折扣率必須介於 0 與 1 之間'

print('✅ 沙盒驗證：所有單元測試通過！')