"""
完整銜接流程：Parser 接進「LLM 生成設計書」的舊流程

原本：     agent.py (原始碼文字) ----------------------> LLM -> raw.json -> validate -> Excel
現在：     agent.py -> Parser(IR) -> build_llm_context -> LLM -> raw.json -> validate
                     \\_______________ cross_check (拿 IR 反查 raw.json) ______/
                                                                           -> Excel

Parser 在這裡做兩件事，不是取代 LLM：
  1. 生成前：把「結構事實」(class/method/field/try-finally...) 整理成精簡摘要餵給 LLM，
     取代直接丟原始碼全文，降低 LLM 看漏或編造結構的機率。
  2. 生成後：LLM 寫完 raw.json 後，用同一份 IR 反查每一列「フィールド」提到的字眼是否
     真的在程式碼裡出現過，抓出可能的幻覺（但概念性摘要本來就會被標記，僅供複核用）。

執行方式：
    python -m examples.run_llm_pipeline
"""
import json
from pathlib import Path
import datetime

from src.ingestion.parser.factory import ParserFactory
import src.ingestion.parser.python_parser  # noqa: F401 (自動註冊)
from src.ingestion.bridge.design_doc_verifier import cross_check
from src.core.llm_router import router
from src.ingestion.schema.screen_item import DesignItem
from src.core.tools.tools import validate_design_json, generate_excel


PROMPT_TEMPLATE = """你是資深系統分析師，請根據以下程式碼結構摘要，
撰寫一份詳細設計書。每一列需包含：No, 項目名称, 分類, 必須, 桁数, フォーマット, テーブル, フィールド, 備考。
只根據摘要中出現的事實撰寫，不要編造摘要沒有提到的欄位或方法。

{context}

請輸出符合以下 JSON schema 的內容：
{{"items": [{{"No": int, "項目名称": str, "分類": str, "必須": "是"|"否",
"桁数": str, "フォーマット": str, "テーブル": str, "フィールド": str, "備考": str}}]}}
"""


def call_llm_to_generate_design_doc(prompt: str) -> str:
    """
    在這裡接上你實際的 LLM 呼叫。
    回傳的字串必須是合法 JSON 字串。
    """
    structured_llm = router.with_structured_output(DesignItem)

    response = structured_llm.invoke(prompt)
    print(response)
    artifact_dir = Path("src/ingestion/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = artifact_dir / f"design_doc_{timestamp}.json"

    # 確保寫入的是合法的 JSON 內容
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(response.content, f, ensure_ascii=False, indent=2)
    return response.content


def run(source_path: str):
    with open(source_path, encoding="utf-8") as f:
        source = f.read()

    # 1. Parser: 原始碼 → IR
    parser = ParserFactory.get_by_language("python")
    module = parser.parse(source, filename=source_path.split("/")[-1])

    # 2. IR → LLM 上下文摘要（取代丟整份原始碼）
    # context = build_llm_context(module)
    # prompt = PROMPT_TEMPLATE.format(context=context)

    # 3. 呼叫 LLM 生成設計書 JSON
    # 若要改回真實 LLM 呼叫，可取消下面註解並改用 call_llm_to_generate_design_doc(prompt)
    raw_json_str = json.dumps({
  "items": [
    {
      "No": 1,
      "項目名称": "State",
      "分類": "类",
      "必須": "是",
      "桁数": "C1",
      "フォーマット": "TypedDict",
      "テーブル": "N/A",
      "フィールド": "代理状态定义",
      "備考": "LangGraph状态图的TypedDict状态"
    },
    {
      "No": 2,
      "項目名称": "messages",
      "分類": "属性",
      "必須": "是",
      "桁数": "C1.F1",
      "フォーマット": "Annotated[list, add_messages]",
      "テーブル": "State",
      "フィールド": "消息列表",
      "備考": "使用add_messages注解，用于累积消息"
    },
    {
      "No": 3,
      "項目名称": "Agent",
      "分類": "类",
      "必須": "是",
      "桁数": "C2",
      "フォーマット": "class",
      "テーブル": "N/A",
      "フィールド": "代理核心类",
      "備考": "负责构建和管理LangGraph代理"
    },
    {
      "No": 4,
      "項目名称": "tools",
      "分類": "属性",
      "必須": "是",
      "桁数": "C2.F1",
      "フォーマット": "list",
      "テーブル": "Agent",
      "フィールド": "工具列表",
      "備考": "包含get_weather, search_official_knowledge_base, validate_design_json, generate_excel以及可选的mcp_tools"
    },
    {
      "No": 5,
      "項目名称": "tool_node",
      "分類": "属性",
      "必須": "是",
      "桁数": "C2.F2",
      "フォーマット": "ToolNode",
      "テーブル": "Agent",
      "フィールド": "工具节点",
      "備考": "基于Agent的tools属性创建"
    },
    {
      "No": 6,
      "項目名称": "graph",
      "分類": "属性",
      "必須": "是",
      "桁数": "C2.F3",
      "フォーマット": "langgraph.graph.StateGraph",
      "テーブル": "Agent",
      "フィールド": "图对象",
      "備考": "通过_build_graph方法构建"
    },
    {
      "No": 7,
      "項目名称": "compiler",
      "分類": "属性",
      "必須": "是",
      "桁数": "C2.F4",
      "フォーマット": "DynamicGraphCompiler",
      "テーブル": "Agent",
      "フィールド": "动态图编译器",
      "備考": "使用State作为状态模式"
    },
    {
      "No": 8,
      "項目名称": "langfuse",
      "分類": "属性",
      "必須": "是",
      "桁数": "C2.F5",
      "フォーマット": "Langfuse",
      "テーブル": "Agent",
      "フィールド": "Langfuse实例",
      "備考": "用于可观测性，通过环境变量LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST初始化"
    },
    {
      "No": 9,
      "項目名称": "router",
      "分類": "属性",
      "必須": "是",
      "桁数": "C2.F6",
      "フォーマット": "Runnable",
      "テーブル": "Agent",
      "フィールド": "LLM路由器",
      "備考": "绑定了Agent的tools属性"
    },
    {
      "No": 10,
      "項目名称": "__init__",
      "分類": "方法",
      "必須": "是",
      "桁数": "C2.M1",
      "フォーマット": "constructor",
      "テーブル": "Agent",
      "フィールド": "构造函数",
      "備考": "初始化Agent实例"
    },
    {
      "No": 11,
      "項目名称": "mcp_tools",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M1.P1",
      "フォーマット": "list",
      "テーブル": "Agent",
      "フィールド": "MCP工具列表",
      "備考": "用于扩展Agent的工具集"
    },
    {
      "No": 12,
      "項目名称": "_model",
      "分類": "方法",
      "必須": "是",
      "桁数": "C2.M2",
      "フォーマット": "method",
      "テーブル": "Agent",
      "フィールド": "私有模型方法",
      "備考": "内部方法，可能返回一个Runnable"
    },
    {
      "No": 13,
      "項目名称": "call",
      "分類": "方法",
      "必須": "是",
      "桁数": "C2.M2.M1",
      "フォーマット": "method",
      "テーブル": "Agent",
      "フィールド": "模型调用方法",
      "備考": "嵌套在_model方法中，用于处理状态和配置"
    },
    {
      "No": 14,
      "項目名称": "state",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M2.M1.P1",
      "フォーマット": "State",
      "テーブル": "Agent",
      "フィールド": "当前状态",
      "備考": "代理的当前运行状态"
    },
    {
      "No": 15,
      "項目名称": "config",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M2.M1.P2",
      "フォーマット": "RunnableConfig",
      "テーブル": "Agent",
      "フィールド": "运行配置",
      "備考": "LangChain Runnable的配置对象"
    },
    {
      "No": 16,
      "項目名称": "_build_graph",
      "分類": "方法",
      "必須": "是",
      "桁数": "C2.M3",
      "フォーマット": "method",
      "テーブル": "Agent",
      "フィールド": "构建图",
      "備考": "私有方法，用于构建LangGraph图结构"
    },
    {
      "No": 17,
      "項目名称": "deploy_or_update_flow",
      "分類": "方法",
      "必須": "是",
      "桁数": "C2.M4",
      "フォーマット": "method",
      "テーブル": "Agent",
      "フィールド": "部署或更新流程",
      "備考": "用于动态更新代理的流程图"
    },
    {
      "No": 18,
      "項目名称": "ui_graph_json",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M4.P1",
      "フォーマット": "unknown",
      "テーブル": "Agent",
      "フィールド": "UI图JSON",
      "備考": "从UI界面获取的图结构定义"
    },
    {
      "No": 19,
      "項目名称": "tools_list",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M4.P2",
      "フォーマット": "unknown",
      "テーブル": "Agent",
      "フィールド": "工具列表",
      "備考": "用于流程的工具列表"
    },
    {
      "No": 20,
      "項目名称": "model",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M4.P3",
      "フォーマット": "unknown",
      "テーブル": "Agent",
      "フィールド": "模型",
      "備考": "用于流程的语言模型"
    },
    {
      "No": 21,
      "項目名称": "ainvoke",
      "分類": "方法",
      "必須": "是",
      "桁数": "C2.M5",
      "フォーマット": "async method",
      "テーブル": "Agent",
      "フィールド": "异步调用",
      "備考": "异步执行代理图，包含错误处理和图初始化检查"
    },
    {
      "No": 22,
      "項目名称": "inputs",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M5.P1",
      "フォーマット": "unknown",
      "テーブル": "Agent",
      "フィールド": "输入",
      "備考": "代理的输入数据"
    },
    {
      "No": 23,
      "項目名称": "config",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M5.P2",
      "フォーマット": "dict",
      "テーブル": "Agent",
      "フィールド": "配置",
      "備考": "运行配置字典"
    },
    {
      "No": 24,
      "項目名称": "控制流",
      "分類": "控制流",
      "必須": "是",
      "桁数": "C2.M5.CF1",
      "フォーマット": "if/try/finally/try/except",
      "テーブル": "Agent",
      "フィールド": "流程控制",
      "備考": "if(not self.graph) | try/finally | try/except(Exception)"
    },
    {
      "No": 25,
      "項目名称": "astream",
      "分類": "方法",
      "必須": "是",
      "桁数": "C2.M6",
      "フォーマット": "async method",
      "テーブル": "Agent",
      "フィールド": "异步流",
      "備考": "异步流式执行代理图，包含错误处理和图初始化检查"
    },
    {
      "No": 26,
      "項目名称": "inputs",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M6.P1",
      "フォーマット": "unknown",
      "テーブル": "Agent",
      "フィールド": "输入",
      "備考": "代理的输入数据"
    },
    {
      "No": 27,
      "項目名称": "config",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M6.P2",
      "フォーマット": "dict",
      "テーブル": "Agent",
      "フィールド": "配置",
      "備考": "运行配置字典"
    },
    {
      "No": 28,
      "項目名称": "stream_mode",
      "分類": "参数",
      "必須": "是",
      "桁数": "C2.M6.P3",
      "フォーマット": "str",
      "テーブル": "Agent",
      "フィールド": "流模式",
      "備考": "指定流的模式"
    },
    {
      "No": 29,
      "項目名称": "控制流",
      "分類": "控制流",
      "必須": "是",
      "桁数": "C2.M6.CF1",
      "フォーマット": "if/try/finally/for/try/except",
      "テーブル": "Agent",
      "フィールド": "流程控制",
      "備考": "if(not self.graph) | try/finally | for(chunk in self.graph.astream(inputs, config=config, stream_mode=stream_mode)) | try/except(Exception)"
    }
  ]
}, ensure_ascii=False, indent=2)

    # 4. 用既有的 validate_design_json 做 schema 強校驗
    validated_json_str = validate_design_json.invoke({"raw_json_str": raw_json_str})
    design_doc = json.loads(validated_json_str)

    # 5. 用 IR 反查，抓可能的幻覺（不擋流程，只是警告）
    warnings = cross_check(design_doc, module)
    for w in warnings:
        print("⚠️ ", w)

    # 6. 產生 Excel
    result = generate_excel.invoke(
        {"json_str": validated_json_str, "template_name": "詳細設計書.xlsx"}
    )
    print(result)


if __name__ == "__main__":
    run("src/core/agent.py")