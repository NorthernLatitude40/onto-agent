import inspect
import os
import re
import types
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import types as genai_types
from supabase import Client, create_client


class SkillLibrary:
    """Voyager 技能庫管理器：負責技能的向量化、Supabase 存取與記憶體動態載入。"""

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        gemini_api_key: str,
        embedding_model: str = "gemini-embedding-001",
        skills_dir: Optional[str] = "src/core/voyager_agent/skills_storage",
    ):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.ai_client = genai.Client(api_key=gemini_api_key)
        self.embedding_model = embedding_model
        self.skills_dir = skills_dir

        # 若指定了本地備份路徑，自動建立目錄
        if self.skills_dir:
            os.makedirs(self.skills_dir, exist_ok=True)

    def _get_embedding(self, text: str) -> List[float]:
        """使用 Gemini 生成 1536 維度的向量以匹配 Supabase 的 vector(1536) 欄位"""
        response = self.ai_client.models.embed_content(
            model=self.embedding_model,
            contents=text,
            config=genai_types.EmbedContentConfig(
                output_dimensionality=1536  # 強制轉為 1536 維度
            ),
        )
        return response.embeddings[0].values

    def add_skill(
        self,
        name: str,
        description: str,
        code: str,
    ) -> Dict[str, Any]:
        """保存技能至 Supabase 資料庫（含 code 欄位），並選擇性同步寫入本地備份 .py 檔"""

        # 1. 可選：寫入本地備份檔（僅供開發檢視）
        if self.skills_dir:
            safe_name = re.sub(r"[^\w\-_]", "_", name.lower())
            file_path = os.path.join(self.skills_dir, f"{safe_name}.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f'"""\n技能名稱: {name}\n描述: {description}\n"""\n\n')
                f.write(code)

        # 2. 生成 Embedding 向量
        embedding = self._get_embedding(description)

        # 3. 寫入 Supabase
        data = {
            "name": name,
            "description": description,
            "embedding": embedding,
            "code": code,
            "updated_at": "now()",
        }

        response = (
            self.supabase.table("voyager_skills")
            .upsert(data, on_conflict="name")
            .execute()
        )
        print(f"✅ 成功將技能 '{name}' 存入 Supabase 資料庫。")
        return response.data

    def load_skill_from_code(
        self,
        skill_name: str,
        code_str: str,
        func_name: Optional[str] = None
    ) -> Callable:
        """從 Supabase 讀取的程式碼字串動態載入技能，返回可調用的函數對象。

        Args:
            skill_name: 技能名稱 (作為動態模組的唯一識別名稱)
            code_str: 從資料庫 (Supabase) 拿到的 Python 原始碼字串
            func_name: 要載入的函數名稱，若為 None 則預設尋找同名函數或模組內第一個函數
        """
        module_name = f"dynamic_skill_{skill_name}"
        module = types.ModuleType(module_name)

        # 1. 在記憶體虛擬模組中編譯並執行 code
        try:
            exec(code_str, module.__dict__)
        except Exception as e:
            raise RuntimeError(
                f"動態載入技能 '{skill_name}' 失敗，程式碼語法錯誤: {e}"
            )

        # 2. 獲取指定的函數（預設尋找同名函數）
        target_func_name = func_name or skill_name
        if hasattr(module, target_func_name):
            return getattr(module, target_func_name)

        # 3. 若無同名函數，自動搜尋模組內第一個定義的函數
        functions = [
            obj
            for name, obj in inspect.getmembers(module)
            if inspect.isfunction(obj) and obj.__module__ == module_name
        ]

        if not functions:
            raise ValueError(f"技能 '{skill_name}' 的程式碼中未找到可調用的函數")

        return functions[0]

    def retrieve_skills(self, task_description: str, threshold: float = 0.82):
        # 1. 生成当前 task_description 的 embedding 向量
        query_vector = self._get_embedding(task_description)

        # 2. 调用 Supabase RPC 函数进行向量余弦相似度比对
        response = self.supabase.rpc(
            "match_skills",
            {
                "query_embedding": query_vector,
                "match_threshold": threshold,  # 高于 0.82 才返回
                "match_count": 1
            }
        ).execute()

        return response.data

    def get_skill_by_name(self, name: str) -> dict:
        """根據名稱取得單一技能"""
        response = (
            self.supabase.table("voyager_skills")
            .select("*")
            .eq("name", name)
            .single()
            .execute()
        )
        return response.data

    def get_all_skills(self) -> List[dict]:
        """取得所有已儲存的技能清單"""
        response = self.supabase.table("voyager_skills").select("*").execute()
        return response.data


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    print("🚀 初始化 SkillLibrary...")
    manager = SkillLibrary(
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        gemini_api_key=GEMINI_API_KEY,
    )

    print("存入測試技能...")
    test_code = (
        "def calculate_monthly_sales(sales_list):\n"
        "    '''計算月度總銷售額額外邏輯'''\n"
        "    return sum(sales_list)\n"
    )
    manager.add_skill(
        name="calculate_monthly_sales",
        description="Calculate the total sales amount for the current month for mobile phone devices.",
        code=test_code,
    )

    print("\n🔍 從 Supabase 取出並動態加載執行技能...")
    skill_data = manager.get_skill_by_name("calculate_monthly_sales")

    # 記憶體動態加載技能
    sales_func = manager.load_skill_from_code(
        skill_name=skill_data["name"], 
        code_str=skill_data["code"]
    )

    # 測試動態呼叫
    res = sales_func([1200, 3500, 4800])
    print(f"🎯 技能執行結果: {res}")