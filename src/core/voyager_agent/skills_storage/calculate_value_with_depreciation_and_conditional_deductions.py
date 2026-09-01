"""
技能名稱: calculate_value_with_depreciation_and_conditional_deductions
描述: 此函數技能用於計算一個初始值的最終估價，透過應用一系列可配置的折舊和扣除規則。它能夠處理基於時間週期（例如每N個月折舊X%）的百分比折舊，以及基於特定條件（例如存在缺陷時扣除固定金額）的固定金額扣除。此外，它還能確保最終估價不低於預設的最低值，並在中間計算步驟中防止數值變為負數。此技能廣泛適用於資產估價、商品回收、保險理賠計算等需要多階段價值調整的場景。
"""

import math

def calculate_trade_in_value(original_price: float, months_used: int, has_screen_scratches: bool) -> float:
    """
    计算二手手机的回收折旧估价。

    该工具接收以下参数：
    - original_price (float): 手机的原价。
    - months_used (int): 手机已使用月数。
    - has_screen_scratches (bool): 屏幕是否有划痕。

    计算规则如下：
    - 使用月数每满 6 个月，原价折旧 10%。
    - 如果屏幕有划痕 (has_screen_scratches 为 True)，额外扣除 500 元。
    - 最终折抵金额不能低于 200 元。

    参数:
        original_price (float): 手机的原价。
        months_used (int): 手机已使用月数。
        has_screen_scratches (bool): 屏幕是否有划痕。

    返回:
        float: 最终折抵金额。
    """
    
    # 1. 根据使用月数计算折旧
    # 每满 6 个月，原价折旧 10%。
    six_month_periods = months_used // 6
    depreciation_from_months = six_month_periods * 0.10 * original_price
    
    # 初始估价（扣除使用月数折旧）
    current_value = original_price - depreciation_from_months
    
    # 确保折旧后的金额不会是负数，最低为0，因为后续还有可能扣除划痕费用
    current_value = max(0.0, current_value)

    # 2. 如果屏幕有划痕，额外扣除 500 元
    if has_screen_scratches:
        current_value -= 500
        # 再次确保扣除划痕费用后不会是负数
        current_value = max(0.0, current_value)

    # 3. 最终折抵金额不能低于 200 元
    final_value = max(200.0, current_value)

    return final_value

def run_tests():
    """
    运行自动测试以验证 calculate_trade_in_value 函数的正确性。
    """
    test_cases = [
        # (original_price, months_used, has_screen_scratches, expected_value)
        (5000.0, 3, False, 5000.0),  # 案例1: 无折旧，无划痕
        (5000.0, 15, False, 4000.0), # 案例2: 2个6月周期折旧 (2*10%*5000=1000)，无划痕
        (5000.0, 15, True, 3500.0),  # 案例3: 2个6月周期折旧 (1000)，有划痕 (4000-500=3500)
        (1000.0, 60, False, 200.0),  # 案例4: 10个6月周期折旧 (10*10%*1000=1000)，价值变为0，触及最低200
        (1000.0, 30, True, 200.0),   # 案例5: 5个6月周期折旧 (5*10%*1000=500)，价值500，有划痕 (500-500=0)，触及最低200
        (100.0, 1, False, 200.0),    # 案例6: 原价很低，无折旧无划痕，直接触及最低200
        (600.0, 1, True, 200.0),     # 案例7: 原价较低，无折旧，有划痕 (600-500=100)，触及最低200
        (2000.0, 12, False, 1600.0), # 案例8: 2个6月周期折旧 (2*10%*2000=400)，无划痕 (2000-400=1600)
        (2000.0, 12, True, 1100.0),  # 案例9: 2个6月周期折旧 (400)，有划痕 (1600-500=1100)
        (500.0, 0, False, 500.0),    # 案例10: 全新，无划痕
        (500.0, 0, True, 200.0),     # 案例11: 全新，有划痕 (500-500=0)，触及最低200
        (200.0, 0, False, 200.0),    # 案例12: 原价恰好为最低值，无折旧无划痕
        (200.0, 0, True, 200.0),     # 案例13: 原价恰好为最低值，无折旧，有划痕 (200-500=-300 -> 0)，触及最低200
        (10000.0, 72, False, 200.0), # 案例14: 12个6月周期折旧 (12*10%*10000=12000)，价值变为-2000 -> 0，触及最低200
    ]

    print("正在运行 calculate_trade_in_value 函数的测试...")
    all_passed = True
    for i, (original_price, months_used, has_screen_scratches, expected_value) in enumerate(test_cases):
        actual_value = calculate_trade_in_value(original_price, months_used, has_screen_scratches)
        
        # 使用 math.isclose 进行浮点数比较，以避免精度问题
        if not math.isclose(actual_value, expected_value, rel_tol=1e-9, abs_tol=0.0):
            print(f"测试案例 {i+1} 失败:")
            print(f"  输入: 原价={original_price}, 使用月数={months_used}, 屏幕有划痕={has_screen_scratches}")
            print(f"  预期值: {expected_value}, 实际值: {actual_value}")
            all_passed = False
        # else:
        #     print(f"测试案例 {i+1} 通过: {actual_value}")

    if all_passed:
        print("所有测试均通过！")
    else:
        print("部分测试失败。")

# 当脚本直接执行时，运行测试
if __name__ == "__main__":
    run_tests()