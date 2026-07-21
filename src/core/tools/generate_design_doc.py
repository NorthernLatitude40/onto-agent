"""
完整銜接流程：Parser 接進專案主流程

執行方式：
    python -m examples.run_llm_pipeline
"""
import json
from pathlib import Path
import datetime

from src.ingestion.parser.factory import ParserFactory
import src.ingestion.parser.python_parser  # noqa: F401 (自動註冊)
from src.ingestion.bridge.llm_context_builder import build_llm_context
from src.ingestion.bridge.design_doc_verifier import cross_check
from src.core.llm_router import router
from src.ingestion.schema.screen_item import DesignItem
from src.core.tools.tools import validate_design_json, generate_excel
from langchain_core.tools import tool

@tool
def generate_design_doc(
    source_path: str
) -> str:
    """
    根據 Python 原始碼生成詳細設計書。

    Returns:
        詳細設計書(JSON + Excel)
    """
    with open(source_path, encoding="utf-8") as f:
        source = f.read()

    # 1. Parser 解析原始碼為結構事實 (IR)
    parser = ParserFactory.get_by_language("python")
    module = parser.parse(source, filename=source_path.split("/")[-1])
    
    # 2. IR -> Context 生成精簡摘要
    context = build_llm_context(module)
    prompt = PROMPT_TEMPLATE.format(context=context)

    # 3. 呼叫 LLM 產出原始 JSON 字串（含欄位標準化）
    raw_json_str = call_llm_to_generate_design_doc(prompt)

    # 4. 統一透過工具進行 Pydantic 全域驗證
    try:
        validated_json = validate_design_json.invoke(
            {"raw_json_str": raw_json_str}
        )
    except Exception as e:
        print(f"❌ Design JSON 驗證失敗: {e}\n原始內容:\n{raw_json_str}")
        raise e

    design_doc = json.loads(validated_json)

    # 5. Cross Check 拿 IR 反查是否有幻覺欄位
    warnings = cross_check(design_doc, module)

    # 6. 生成 Excel
    excel_path = generate_excel.invoke(
        {
            "json_str": validated_json,
            "template_name": "詳細設計書.xlsx",
        }
    )

    return json.dumps(
        {
            "excel": excel_path,
            "warnings": warnings,
        },
        ensure_ascii=False,
    )

PROMPT_TEMPLATE = """你是資深系統分析師，請根據以下程式碼結構摘要，
撰寫一份詳細設計書。每一列需包含：No, 项目名称, 分分类, 必須, 桁数, フォーマット, テーブル, フィールド, 備考。
只根據摘要中出現的事實撰寫，不要編造摘要沒有提到的欄位或方法。

{context}

請輸出符合以下 JSON schema 的內容：
{{"items": [{{"No": int, "项目名称": str, "分类": str, "必须": "是"|"否",
"桁数": str, "フォーマット": str, "テーブル": str, "フィールド": str, "備考": str}}]}}
"""


def call_llm_to_generate_design_doc(prompt: str) -> str:
    """
    負責與 LLM 互動、清洗 Markdown 格式、標準化欄位名稱，
    並將清理後的結果組裝成標準的 {"items": [...]} JSON 字串回傳。
    """
    schema_json = json.dumps(DesignItem.model_json_schema(), ensure_ascii=False, indent=2)
    
    enhanced_prompt = (
        f"{prompt}\n\n"
        f"【強制規定】\n"
        f"你必須輸出一個合法的 JSON 物件，絕對不要包含任何 markdown 程式碼反引號（如 ```json）或額外解釋文字。\n"
        f"該 JSON 必須嚴格符合以下 Pydantic JSON Schema 結構：\n"
        f"{schema_json}"
    )

    response = router.invoke(enhanced_prompt)
    print("--- LLM 原始回應 ---")
    print(response)

    # 1. 取得原始內容，並相容 content 為 str 或 list 的情況
    content = response.content if hasattr(response, "content") else response
    
    if isinstance(content, list):
        raw_text = "".join([item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in content])
    else:
        raw_text = str(content)

    # 2. 清洗 Markdown 符號
    cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(cleaned_text)
    except Exception as e:
        raise ValueError(f"LLM 產出的內容無法解析為 JSON: {e}\n原始輸出文字為:\n{raw_text}")
    
    # 3. 確保資料結構包在 {"items": [...]} 內
    if isinstance(data, dict) and "items" in data:
        items_raw = data["items"]
    elif isinstance(data, list):
        items_raw = data
    else:
        items_raw = [data]

    # 4. 欄位名稱對應與標準化（處理 LLM 偶爾大小寫或拼寫不一致的問題）
    normalized_items = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        
        normalized_item = {}
        for k, v in item.items():
            k_lower = k.lower()
            if k_lower in ["fields", "field", "字段", "フィールド"]:
                normalized_item["フィールド"] = v
            elif k_lower in ["table", "tables", "テーブル", "表格"]:
                normalized_item["テーブル"] = v
            else:
                normalized_item[k] = v
        
        normalized_items.append(normalized_item)

    output_data = {"items": normalized_items}

    # 5. 寫入實體 JSON 檔案備查
    artifact_dir = Path("src/ingestion/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = artifact_dir / f"design_doc_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 6. 回傳標準化後的 JSON 字串交給下一步的驗證工具
    return json.dumps(output_data, ensure_ascii=False, indent=2)