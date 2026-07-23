"""
完整銜接流程：Parser 接進專案主流程

變更說明（相對於原版）：
  1. PROMPT_TEMPLATE 原本用中日文表頭原文（"項目名称"/"桁数"/…）手寫欄位說明，
     但後面 call_llm_to_generate_design_doc() 又把 DesignItem.model_json_schema()
     整段附加進最終 prompt，要求輸出符合 canonical key（"item_name"/"field_code"/…）。
     兩段指令互相矛盾，LLM 有時聽前段、有時聽後段，輸出不穩定。
     現在改成 _build_field_instructions()，直接從 DesignItem 的欄位定義
     （含 description，如 "項目名稱 (Canonical: item_name)"）動態產生欄位說明，
     確保 prompt 裡永遠只有一套欄位名稱、且與 schema 同步；改 schema 不用記得
     回來改 prompt。
     is_group 是渲染用的旗標，不需要 LLM 產生，會被排除在欄位說明外
     （DesignItem 有預設值 False，缺省即可通過驗證）。
  2. call_llm_to_generate_design_doc() 裡原本手寫的「欄位名稱對應」
     （只處理 field/table 兩種別名）改用 src.ontology.screen_dict 的
     HeaderSemanticResolver，跟 tools.py／design_doc_builder.py 共用同一份
     HEADER_ONTOLOGY，涵蓋全部 9 個欄位、且繁簡/大小寫/空白都正規化過。
     LLM 不管輸出 "項目名称" 還是 "item_name" 還是 "フィールド"，這裡都會
     統一收斂成 canonical key 再交給 validate_design_json。

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
from src.ontology.screen_dict import HeaderSemanticResolver
from src.core.tools.tools import validate_design_json, generate_excel
from langchain_core.tools import tool

_header_resolver = HeaderSemanticResolver()

# 不需要（也不該）由 LLM 自行判斷的欄位：
#   no          由程式流水號賦予，不需要 LLM 猜
#   is_group    是 Excel 渲染用的旗標，有預設值 False，交給
#               design_doc_builder.py 那種確定性流程去標記即可，
#               LLM 自由生成的設計書不該自己決定分組
_LLM_EXCLUDED_FIELDS = {"is_group"}


def _build_field_instructions() -> str:
    """從 DesignItem 動態產生欄位說明，取代寫死在 prompt 裡的欄位清單。"""
    lines = []
    for name, finfo in DesignItem.model_fields.items():
        if name in _LLM_EXCLUDED_FIELDS:
            continue
        desc = finfo.description or name
        required = "必填" if finfo.is_required() else "選填"
        lines.append(f"- {name}：{desc}（{required}）")
    return "\n".join(lines)


PROMPT_TEMPLATE = """你是資深系統分析師，請根據以下程式碼結構摘要，撰寫一份詳細設計書。

每一列請使用以下欄位（請直接使用這裡列出的英文 key 當 JSON 的 key，
不要翻譯或改寫成中日文表頭字樣，也不要新增這裡沒有列出的欄位）：
{field_instructions}

只根據摘要中出現的事實撰寫，不要編造摘要沒有提到的欄位或方法。
最終輸出格式必須是 {{"items": [ ... ]}}，本訊息稍後會附上完整的 JSON Schema，
請以該 Schema 為準。

{context}
"""


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
    prompt = PROMPT_TEMPLATE.format(
        field_instructions=_build_field_instructions(), context=context
    )

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

    # 4. 欄位名稱正規化：改用 HeaderSemanticResolver，
    #    跟 tools.py／design_doc_builder.py 共用同一份 HEADER_ONTOLOGY，
    #    不論 LLM 輸出的 key 是中日文表頭原文、canonical key、或大小寫拼寫不一致，
    #    這裡都統一收斂成 canonical key（no/item_name/category/…）。
    #    resolve() 找不到對應概念時保留原 key，避免真的有新欄位被誤刪。
    normalized_items = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        normalized_item = {
            (_header_resolver.resolve(k) or k): v for k, v in item.items()
        }
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