"""
完整銜接流程：Parser 接進專案主流程並產出自然語言詳細設計書
"""
import datetime
import json
from pathlib import Path

from langchain_core.tools import tool

import src.ingestion.parser.python_parser
import src.ingestion.parser.react_parser  # noqa: F401 (自動註冊)
from src.core.llm_router import router
from src.core.tools.tools import generate_excel, validate_design_json
from src.ingestion.bridge.design_doc_verifier import cross_check
from src.ingestion.bridge.llm_context_builder import build_llm_context
from src.ingestion.parser.factory import ParserFactory
from src.ingestion.schema.screen_item import DesignItem
from src.ontology.screen_dict import HeaderSemanticResolver

_header_resolver = HeaderSemanticResolver()

_LLM_EXCLUDED_FIELDS = {"is_group"}


def _build_field_instructions() -> str:
    """從 DesignItem 動態產生欄位說明。"""
    lines = []
    for name, finfo in DesignItem.model_fields.items():
        if name in _LLM_EXCLUDED_FIELDS:
            continue
        desc = finfo.description or name
        required = "必填" if finfo.is_required() else "選填"
        lines.append(f"- {name}：{desc}（{required}）")
    return "\n".join(lines)


PROMPT_TEMPLATE = """你是資深系統分析師與技術文件撰寫員（Technical Writer）。
請根據以下提供的程式碼結構摘要（AST Context），撰寫一份適用於系統詳細設計書（Excel）的自然語言畫面與機能項目清單。

【自然語言轉譯核心規則】：
1. 嚴禁直接將原始程式碼變數、Hook 或元件名稱直接作為「項目名稱」或「說明」輸出！
   - ❌ 錯誤：item_name="useNodesState", remarks="從 @xyflow/react 導入"
   - ✅ 正確：item_name="繪圖畫布節點狀態管理", category="State", remarks="負責儲存與更新畫面上所有節點的位置、屬性與渲染狀態"
2. 請將 AST 摘要中的技術符號與 UI 表單元素翻譯為業務/UI看得懂的語意描述：
   - ReactFlow ➔ 畫布繪圖主區域
   - Controls ➔ 畫布操作工具列（放大/縮小/重設）
   - `<select>` ➔ 模型名稱選擇下拉選單
   - `<textarea>` ➔ 提示詞 (Prompt) 輸入框
3. 若 AST Context 中含有表單元件（如 input、select、textarea），請務必精準產出其對應的欄位屬性（長度、預設格式等）。

【嚴格欄位 Key 完整性規範】：
每一個 JSON 物件**必須包含下列所有的 Key**，絕對不允許漏掉任何 Key！
若該項目無對應資料（例如非資料庫連動欄位）：
- 字串型別欄位請務必填入空字串 `""`（絕對不可以省略欄位！）
- 布爾型別欄位請填入 `false`
- `no` 請依照順序給予整數編號 (1, 2, 3...)

欄位清單如下：
{field_instructions}

最終輸出格式必須嚴格是 {{"items": [ ... ]}}。

【程式碼結構摘要 (AST Context)】：
{context}
"""

@tool
def generate_design_doc(
    source_path: str
) -> str:
    """
    根據原始碼檔案生成詳細設計書 (JSON + Excel)。
    """
    with open(source_path, encoding="utf-8") as f:
        source = f.read()

    # 1. Parser 解析原始碼為結構事實 (IR)
    filename = source_path.split("/")[-1]
    parser = ParserFactory.get_by_filename(filename)
    module = parser.parse(source, filename=filename)

    # 2. IR -> Context 生成包含業務預推導的自然語言摘要
    context = build_llm_context(module)
    prompt = PROMPT_TEMPLATE.format(
        field_instructions=_build_field_instructions(),
        context=context
    )

    # 3. 呼叫 LLM 生成設計書 JSON
    raw_json_str = call_llm_to_generate_design_doc(prompt)

    # 4. Pydantic 驗證
    try:
        validated_json = validate_design_json.invoke(
            {"raw_json_str": raw_json_str}
        )
    except Exception as e:
        print(f"❌ Design JSON 驗證失敗: {e}\n原始內容:\n{raw_json_str}")
        raise
    # 判斷驗證後的結果型態，確保 design_doc 是 dict、json_str 是 str
    if isinstance(validated_json, dict):
        design_doc = validated_json
        json_str_for_excel = json.dumps(validated_json, ensure_ascii=False)
    elif isinstance(validated_json, str):
        design_doc = json.loads(validated_json)
        json_str_for_excel = validated_json
    else:
        # 若傳回的是 Pydantic Model 物件
        design_doc = validated_json.model_dump()
        json_str_for_excel = validated_json.model_dump_json()

    # 5. Cross Check 比對幻覺
    warnings = cross_check(design_doc, module)

    # 6. 生成 Excel
    print(f"DEBUG: json_str_for_excel type is {type(json_str_for_excel)}")
    try:
        excel_path = generate_excel(
            json_str=json_str_for_excel,
            template_name="詳細設計書.xlsx"
        )
    except Exception as e:
        excel_path = None
        warnings.append(f"Excel 生成失敗: {e}")

    return json.dumps({
        "design_json": design_doc,   # 已驗證過的結構化資料
        "excel": excel_path,
        "warnings": warnings,
    }, ensure_ascii=False)

def call_llm_to_generate_design_doc(prompt: str) -> str:
    schema_json = json.dumps(
        DesignItem.model_json_schema(), ensure_ascii=False, indent=2
    )

    enhanced_prompt = (
        f"{prompt}\n\n"
        f"【強制格式規定】\n"
        f"你必須輸出一個合法的 JSON 物件，絕對不要包含任何 markdown 程式碼反引號（如 ```json）或額外文字。\n"
        f"請嚴格遵守以下 Pydantic JSON Schema：\n"
        f"{schema_json}"
    )

    response = router.invoke(enhanced_prompt)

    print("--- LLM 原始回應 ---")
    print(response)

    raw_text = ""

    # 1. 優先從 content 提取文字內容
    if hasattr(response, "content") and response.content:
        content = response.content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(item["text"])
                elif hasattr(item, "text"):
                    parts.append(item.text)
                else:
                    parts.append(str(item))
            raw_text = "".join(parts)
        else:
            raw_text = str(content)

    # 2. 若 content 為空，嘗試從 tool_calls 提取（處理 LLM 自行發起 Tool Call 的情況）
    elif hasattr(response, "tool_calls") and response.tool_calls:
        first_call = response.tool_calls[0]
        args = first_call.get("args", {})
        if "raw_json_str" in args:
            raw_text = args["raw_json_str"]
        else:
            raw_text = json.dumps(args, ensure_ascii=False)

    # 清理 markdown 標籤
    cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()

    # 3. 驗證是否有成功拿到內容
    if not cleaned_text:
        raise ValueError(
            f"LLM 未能生成任何有效文字或 Tool Call 內容，原始 response: {response}"
        )

    # 4. JSON 解析驗證
    try:
        data = json.loads(cleaned_text)
    except (ImportError, Exception) as e:
        raise ValueError(f"LLM 回應無法解析為 JSON: {e}\n原始內容:\n{raw_text}")

    # 5. 資料結構正規化
    if isinstance(data, dict) and "items" in data:
        items_raw = data["items"]
    elif isinstance(data, list):
        items_raw = data
    else:
        items_raw = [data]

    # 利用 HeaderSemanticResolver 歸一化 Key
    normalized_items = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        normalized_item = {
            (_header_resolver.resolve(k) or k): v for k, v in item.items()
        }
        normalized_items.append(normalized_item)

    output_data = {"items": normalized_items}

    # 6. 保存 Artifact
    artifact_dir = Path("src/ingestion/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = artifact_dir / f"design_doc_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    return json.dumps(output_data, ensure_ascii=False, indent=2)