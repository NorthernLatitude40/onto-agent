from langfuse import Langfuse

# 1. 初始化
langfuse = Langfuse(
    public_key="pk-lf-78ff93f5-789d-4654-a0d9-5ff18d902891",
    secret_key="sk-lf-8269a33c-9840-4666-ac9d-96f222b147bb",
    host="http://localhost:3000",
)

# 2. 使用 create_trace 建立 Trace
trace = langfuse.create_trace(name="Test-Connection")

# 3. 使用 generation 記錄生成結果
trace.generation(
    name="Test-Generation",
    output="Hello Langfuse"
)

# 4. 強制刷新數據發送至服務器
langfuse.flush()

print("測試數據已發送，請刷新 Dashboard 檢查！")