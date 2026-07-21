"""
完整流程展示：Python 原始碼 → Parser (IR) → 設計書 JSON → Excel

執行前請確認：
  1. tools.py 所需套件已安裝（httpx / langchain_core / opencc / openpyxl）
  2. src/config/config.py、src/ingestion/schema/screen_item.py 存在於你的專案中
     （這兩個是 tools.py 原本就依賴的模組，這裡沒有一併提供）
  3. templates/template_1.xlsx 存在，且表頭包含「No、项目名称、分类、必须、
     桁数、フォーマット、テーブル、フィールド、備考」

執行方式：
    python -m examples.run_full_pipeline
"""
import json
import textwrap
from pathlib import Path

from src.ingestion.parser.factory import ParserFactory
import src.ingestion.parser.python_parser  # noqa: F401  (自動註冊 PythonParser)
from src.ingestion.bridge.design_doc_builder import build_design_doc


SOURCE = textwrap.dedent("""
    class Order:
        id: int
        note: str = ""

        def __init__(self, id: int, note: str = ""):
            self.id = id
            self.note = note

        def total(self, items: list) -> int:
            return len(items)
    """)


def main():
    # 1. 解析原始碼 → IR
    parser = ParserFactory.get_by_language("python")
    module = parser.parse(SOURCE, filename="order.py")

    # 2. IR → 設計書 JSON（規則見 design_doc_builder.py）
    design_doc = build_design_doc(module)
    design_doc_json = json.dumps(design_doc, ensure_ascii=False)

    artifact_dir = Path("src/ingestion/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    output_file = artifact_dir / "design_doc.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(design_doc, f, ensure_ascii=False, indent=2)

    print("=== 設計書 JSON ===")
    print(json.dumps(design_doc, ensure_ascii=False, indent=2))

    # 3. 設計書 JSON → Excel（呼叫 tools.py 既有的 generate_excel）
    #    注意：generate_excel 是被 @tool 裝飾過的 LangChain tool，
    #    直接呼叫要用 .invoke(...) 或 .func(...)，視你的 langchain_core 版本而定。
    from core.tools.tools import generate_excel

    result = generate_excel.invoke(
        {"json_str": design_doc_json, "template_name": "template_1.xlsx"}
    )
    print(result)


if __name__ == "__main__":
    main()
