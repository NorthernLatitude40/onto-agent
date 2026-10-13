import os
from supabase import create_client, Client
from openai import OpenAI

# 1. 初始化 Supabase 與 OpenAI 客戶端
SUPABASE_URL = "你的_SUPABASE_URL"
SUPABASE_KEY = "你的_SUPABASE_ANON_KEY_或_SERVICE_ROLE_KEY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI(api_key="你的_OPENAI_API_KEY")

def get_embedding(text: str):
    """生成 1536 維度的向量"""
    response = client.embeddings.create(
        model="text-embedding-3-small", # 或 text-embedding-ada-002
        input=text
    )
    return response.data[0].embedding

# 2. 測試插入一個 Skill
def insert_skill(name, description, file_path, code):
    embedding = get_embedding(description)
    data = {
        "name": name,
        "description": description,
        "file_path": file_path,
        "code": code,
        "embedding": embedding
    }
    res = supabase.table("voyager_skills").insert(data).execute()
    print("插入成功：", res)

# 3. 測試向量檢索（調用你剛剛建立的 RPC 函數）
def search_skills(query_text: str, top_k: int = 3):
    query_embedding = get_embedding(query_text)
    
    # 調用剛建好的 match_voyager_skills 函數
    res = supabase.rpc(
        "match_voyager_skills", 
        {
            "query_embedding": query_embedding,
            "match_count": top_k
        }
    ).execute()
    
    return res.data

# --- 執行測試 ---
# 1. 寫入一個技能
# insert_skill("mine_wood", "Mine wood logs from trees using an axe", "skills/mine_wood.js", "function mineWood() {...}")

# 2. 檢索相關技能
# results = search_skills("How to collect timber from forest?")
# print("檢索結果：", results)