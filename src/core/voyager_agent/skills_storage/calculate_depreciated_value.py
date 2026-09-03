"""
技能名稱: calculate_depreciated_value
描述: 計算資產在經歷線性折舊後的殘值。該函數接受初始價值、已使用時間週期（如月數）、單週期折舊率以及最大折舊上限作為參數，通過線性模型計算總折舊率並應用上限約束，最終返回折舊後的剩餘價值。適用於二手商品回收、資產評估等場景。
"""

def calculate_resale_value(original_price, months_used):
    """
    計算二手手機回收價格。
    
    參數:
    original_price (float): 手機原價
    months_used (int): 使用月數
    
    返回:
    float: 回收價格
    """
    if original_price < 0:
        raise ValueError("原價不能為負數")
    if months_used < 0:
        raise ValueError("使用月數不能為負數")
    
    # 每月折舊率 2.5%
    monthly_depreciation_rate = 0.025
    
    # 計算總折舊率
    total_depreciation_rate = monthly_depreciation_rate * months_used
    
    # 最高折舊不超過 80%
    max_depreciation_rate = 0.80
    if total_depreciation_rate > max_depreciation_rate:
        total_depreciation_rate = max_depreciation_rate
    
    # 計算回收價格
    resale_value = original_price * (1 - total_depreciation_rate)
    
    return resale_value

if __name__ == "__main__":
    # 示例測試
    original_price = 5000.0
    months_used = 12
    
    resale_value = calculate_resale_value(original_price, months_used)
    print(f"原價: {original_price:.2f}")
    print(f"使用月數: {months_used}")
    print(f"回收價格: {resale_value:.2f}")