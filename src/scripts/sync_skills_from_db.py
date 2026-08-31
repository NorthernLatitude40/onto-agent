import os
from dotenv import load_dotenv
from supabase import Client, create_client

SKILLS_DIR = "src/core/voyager_agent/skills_storage"


def sync_skills():
  # 確保環境變數已載入
  load_dotenv()

  supabase_url = os.getenv("SUPABASE_URL")
  supabase_key = os.getenv("SUPABASE_KEY")

  if not supabase_url or not supabase_key:
    raise ValueError("❌ 找不到 SUPABASE_URL 或 SUPABASE_KEY，請檢查 .env 設定")

  supabase: Client = create_client(supabase_url, supabase_key)

  os.makedirs(SKILLS_DIR, exist_ok=True)

  # 1. 從 Supabase 抓取所有技能
  response = supabase.table("voyager_skills").select("*").execute()
  skills = response.data

  print(f"📦 正在從 Supabase 同步 {len(skills)} 個技能到本地...")

  # 2. 將 code 寫入本地 .py 檔案
  for skill in skills:
    name = skill["name"]
    code = skill.get("code", "")
    description = skill.get("description", "")

    file_path = os.path.join(SKILLS_DIR, f"{name}.py")

    # 加上 Docstring 註解
    file_content = f'"""\n{description}\n"""\n\n{code}\n'

    with open(file_path, "w", encoding="utf-8") as f:
      f.write(file_content)

    print(f"  └─ 已更新/建立: {file_path}")

  print("✅ 所有技能同步完成！")


if __name__ == "__main__":
  sync_skills()