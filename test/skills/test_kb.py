import pytest

pytestmark = pytest.mark.integration
import httpx

# 🛠️ 手動填入你的環境變數進行測試
ANYTHINGLLM_BASE_URL = "http://localhost:3001/api/v1"
ANYTHINGLLM_API_KEY = "5CWGCCF-QZMMSTT-HA2ESKA-DG24WBH"  # 👈 記得換成你在後台生成的 Key
WORKSPACE_SLUG = "ticketrules"                  # 👈 換成你建立的工作區名稱 (通常是英文小寫底線)

url = f"{ANYTHINGLLM_BASE_URL}/workspace/{WORKSPACE_SLUG}/chat"
headers = {
    "Authorization": f"Bearer {ANYTHINGLLM_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "message": "退票",       # 👈 請確保 FAQ.txt 裡有這兩個字，或者換成內文有的字
    "mode": "query",
    "model": "current",     # 👈 強制指定使用當前工作區設定的模型
    "temperature": 0.0      # 👈 降低隨機性，讓回應穩定
}

print(f"正在請求 URL: {url}")
try:
    response = httpx.post(url, json=payload, headers=headers, timeout=15)
    print(f"狀態碼: {response.status_code}")
    print("原始回應內容：")
    print(response.text) # 觀察這裏，看 AnythingLLM 到底回傳了什麼
except (RuntimeError, OSError) as e:
    print(f"連線失敗: {e}")