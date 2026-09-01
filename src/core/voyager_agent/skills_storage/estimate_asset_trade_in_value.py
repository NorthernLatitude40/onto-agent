"""
技能名稱: estimate_asset_trade_in_value
描述: 根據資產原始價格、使用月數及外觀狀況（如屏幕損壞程度），估算二手資產的回收折抵價值。該函數採用分段折舊模型：前12個月應用線性加速折舊，超過12個月後應用固定月度折舊率，並根據外觀狀況施加額外扣減，同時設置最低價值下限以防止估值過低。
"""

def estimate_trade_in_value(original_price, usage_months, screen_condition):
    """
    Estimates the trade-in value of a used mobile phone based on its original price,
    usage duration, and screen condition.

    Args:
        original_price (float): The original purchase price of the phone in CNY.
        usage_months (int): The duration of phone usage in months.
        screen_condition (str): The condition of the screen.
                                 Possible values: "perfect", "minor_scratches", "major_cracks".

    Returns:
        float: The estimated trade-in value in CNY, rounded to two decimal places.
    """

    # --- Depreciation Constants ---
    # Percentage of value lost in the first 12 months.
    # This represents a significant initial depreciation.
    FIRST_YEAR_DEPRECIATION_FACTOR = 0.35  # 35% value loss in the first year

    # Monthly depreciation rate for months beyond the first year.
    # Depreciation typically slows down after the initial steep drop.
    MONTHLY_DEPRECIATION_RATE_AFTER_FIRST_YEAR = 0.015  # 1.5% value loss per month

    # --- Condition Adjustment Constants ---
    # Deductions for various screen conditions.
    SCREEN_MINOR_SCRATCH_DEDUCTION = 0.05  # 5% deduction for minor scratches
    SCREEN_MAJOR_CRACK_DEDUCTION = 0.20   # 20% deduction for major cracks

    # Initialize current value with the original price
    current_value = float(original_price)

    # 1. Calculate value based on usage duration
    if usage_months <= 0:
        # If not used, assume it's new, but in a real scenario, an "open box" item might still depreciate slightly.
        # For this model, 0 months means no time-based depreciation.
        pass
    elif usage_months <= 12:
        # For usage within the first year, apply a linear portion of the first year's total depreciation.
        # E.g., 6 months would apply 0.5 * FIRST_YEAR_DEPRECIATION_FACTOR.
        depreciation_factor = FIRST_YEAR_DEPRECIATION_FACTOR * (usage_months / 12.0)
        current_value *= (1 - depreciation_factor)
    else:
        # For usage beyond 12 months
        # First, apply the full first year depreciation
        current_value *= (1 - FIRST_YEAR_DEPRECIATION_FACTOR)

        # Then, calculate and apply depreciation for the remaining months
        remaining_months = usage_months - 12
        depreciation_for_remaining_months = MONTHLY_DEPRECIATION_RATE_AFTER_FIRST_YEAR * remaining_months
        current_value *= (1 - depreciation_for_remaining_months)

    # Ensure the value doesn't drop below a reasonable floor (e.g., 10% of original price).
    # This prevents extremely old or damaged phones from having negative or near-zero value
    # if the depreciation model is too aggressive for extreme cases.
    MIN_VALUE_FLOOR_FACTOR = 0.10
    current_value = max(current_value, original_price * MIN_VALUE_FLOOR_FACTOR)

    # 2. Apply condition adjustments
    if screen_condition == "minor_scratches":
        current_value *= (1 - SCREEN_MINOR_SCRATCH_DEDUCTION)
    elif screen_condition == "major_cracks":
        current_value *= (1 - SCREEN_MAJOR_CRACK_DEDUCTION)
    # If screen_condition is "perfect" or any other unrecognized string, no deduction is applied.

    # Ensure the final estimated value is not negative and round to two decimal places
    return max(0.0, round(current_value, 2))

# --- Example Usage based on the problem description ---
if __name__ == "__main__":
    # Input parameters from the problem description
    original_purchase_price = 5000  # 原始购买价格 (元)
    usage_duration_months = 14      # 使用时长 (个月)
    phone_screen_condition = "minor_scratches" # 屏幕状况 (轻微划痕)

    estimated_trade_in_amount = estimate_trade_in_value(
        original_purchase_price,
        usage_duration_months,
        phone_screen_condition
    )

    # Display the results
    print(f"原始购买价格: {original_purchase_price}元")
    print(f"使用时长: {usage_duration_months}个月")
    # Translate screen_condition for display
    display_screen_condition = {
        "perfect": "完好",
        "minor_scratches": "轻微划痕",
        "major_cracks": "严重裂纹"
    }.get(phone_screen_condition, phone_screen_condition) # Fallback to original string if not found
    print(f"屏幕状况: {display_screen_condition}")
    print(f"估算回收折抵金额: {estimated_trade_in_amount}元")