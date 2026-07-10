from langfuse import Langfuse

# 初始化（確保環境變數已載入，或手動傳入）
langfuse = Langfuse(
    public_key="pk-lf-78ff93f5-789d-4654-a0d9-5ff18d902891",
    secret_key="sk-lf-8269a33c-9840-4666-ac9d-96f222b147bb",
    host="http://localhost:3000",
)

# 測試發送一個簡單的 Trace
trace = langfuse.trace(name="Test-Connection")
trace.generation(name="Test-Generation", output="Hello Langfuse")
langfuse.flush()

print("測試數據已發送，請刷新 Dashboard 檢查！")
