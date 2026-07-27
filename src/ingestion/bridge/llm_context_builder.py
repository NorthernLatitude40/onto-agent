"""
IR (ModuleInfo) → LLM 上下文摘要

取代「把整份原始碼丟給 LLM」的做法：LLM 讀原始碼容易看漏 try/finally、
誤植方法名稱，或憑印象編出程式碼裡沒有的欄位。改成先用 Parser 抽出
「結構事實」，再把這份精簡、消歧義的摘要放進 prompt，LLM 只需要在這些
事實上做語意摘要（分類/備考怎麼寫），不用自己從原始碼重新辨認結構。

輸出格式選 Markdown 而不是 JSON，是因為 LLM 對層級縮排的可讀性通常
比巢狀 JSON 好、也比較省 token。
"""
from __future__ import annotations

from src.ingestion.ir.model import (
    ClassInfo,
    ForStatement,
    IfStatement,
    MethodInfo,
    Statement,
    TryStatement,
    WhileStatement,
)
from typing import Any
from src.ontology.screen_dict import BusinessTermResolver


def _describe_control_flow(statements: list[Statement]) -> list[str]:
    """遞迴列出 method 內用到的控制流語句（給 LLM 知道有沒有 try/finally、迴圈等）"""
    notes: list[str] = []
    for stmt in statements:
        if isinstance(stmt, TryStatement):
            has_finally = bool(stmt.finally_body)
            handler_types = [h.exception_type or "Exception" for h in stmt.handlers]
            desc = "try"
            if handler_types:
                desc += f"/except({', '.join(handler_types)})"
            if has_finally:
                desc += "/finally"
            notes.append(desc)
            notes.extend(_describe_control_flow(stmt.body))
            for h in stmt.handlers:
                notes.extend(_describe_control_flow(h.body))
            notes.extend(_describe_control_flow(stmt.finally_body))
        elif isinstance(stmt, IfStatement):
            notes.append(f"if({stmt.condition})")
            notes.extend(_describe_control_flow(stmt.body))
            notes.extend(_describe_control_flow(stmt.else_body))
        elif isinstance(stmt, ForStatement):
            notes.append(f"for({stmt.target} in {stmt.iterable})")
            notes.extend(_describe_control_flow(stmt.body))
        elif isinstance(stmt, WhileStatement):
            notes.append(f"while({stmt.condition})")
            notes.extend(_describe_control_flow(stmt.body))
    return notes


def _render_method(method: MethodInfo, indent: str = "  ") -> list[str]:
    params = ", ".join(
        f"{p.name}:{p.type}" if p.type else p.name for p in method.parameters
    )
    ret = f" -> {method.return_type}" if method.return_type else ""
    lines = [f"{indent}- def {method.name}({params}){ret}"]

    flow = _describe_control_flow(method.body)
    if flow:
        lines.append(f"{indent}  控制流: {' | '.join(flow)}")

    return lines


def _render_class(clazz: ClassInfo) -> list[str]:
    bases = f"({', '.join(clazz.bases)})" if clazz.bases else ""
    lines = [f"- class {clazz.name}{bases}"]

    for field in clazz.fields:
        type_part = f": {field.type}" if field.type else ""
        default_part = f" = {field.default_value}" if field.default_value else ""
        lines.append(f"  - field {field.name}{type_part}{default_part}")

    for method in clazz.methods:
        lines.extend(_render_method(method))

    return lines



"""
將 Parser 產出的 ModuleInfo IR 轉化成高豐富度的結構化自然語言摘要 (LLM Context)
"""
term_resolver = BusinessTermResolver()


def _render_method(func: Any, indent: str = "  ") -> list[str]:
    lines = []
    func_name = getattr(func, "name", str(func))
    docstring = getattr(func, "docstring", None) or getattr(func, "doc", None)
    args = getattr(func, "args", []) or getattr(func, "params", [])
    
    # 結合 BusinessTerm 推導
    term_info = term_resolver.enrich_field_info(func_name)
    logical_hint = term_info.get("logical_name", func_name)

    lines.append(f"{indent}- **處理/函式名**: `{func_name}` (建議邏輯名稱: {logical_hint})")
    if docstring:
        clean_doc = docstring.strip().replace("\n", " ")
        lines.append(f"{indent}  - **程式碼註解**: {clean_doc}")
    if args:
        lines.append(f"{indent}  - **參數清單**: {', '.join(str(a) for a in args)}")
    return lines


def _render_class(clazz: Any) -> list[str]:
    lines = []
    class_name = getattr(clazz, "name", "UnknownClass")
    docstring = getattr(clazz, "docstring", None)
    methods = getattr(clazz, "methods", []) or getattr(clazz, "functions", [])
    
    term_info = term_resolver.enrich_field_info(class_name)
    logical_hint = term_info.get("logical_name", class_name)

    lines.append(f"- **類別/元件**: `{class_name}` (建議邏輯分類: {logical_hint})")
    if docstring:
        lines.append(f"  - **類別說明**: {docstring.strip()}")
    
    if methods:
        lines.append("  - **內部方法/處理列表**:")
        for m in methods:
            lines.extend(_render_method(m, indent="    "))
    return lines


def build_llm_context(module: Any) -> str:
    """把 ModuleInfo 轉成適合放進 LLM prompt 的自然語言結構摘要。"""
    filename = getattr(module, "filename", "(unknown)")
    lines: list[str] = [f"# 原始碼檔案結構摘要: {filename}", ""]

    imports = getattr(module, "imports", [])
    if imports:
        lines.append("## 外部引用與依賴 (Imports)")
        for imp in imports:
            imp_name = getattr(imp, "name", str(imp))
            term_info = term_resolver.enrich_field_info(imp_name)
            lines.append(f"- `{imp_name}` ➔ 推導元件: {term_info['logical_name']} ({term_info['category']})")
        lines.append("")

    # 🟢 新增：UI 表單與輸入控制項摘要
    all_ui_fields = []
    for comp in getattr(module, "components", []):
        for field in getattr(comp, "ui_fields", []):
            all_ui_fields.append(f"- 【{comp.name}】標籤: `<{field['tag']}>`, 類型: {field['type']}, 變數綁定: `{field['value_binding']}`, 提示字: \"{field['placeholder']}\"")

    if all_ui_fields:
        lines.append("## UI 表單與輸入控制項 (UI Components & Fields)")
        lines.extend(all_ui_fields)
        lines.append("")

    # 2. 解析 Classes / Major Components (包含傳統 Class 與 React 組件)
    classes = getattr(module, "classes", [])
    components = getattr(module, "components", []) # 🟢 支援前端組件欄位
    all_components = classes + components
    if all_components:
        lines.append("## 類別與主 UI 元件 (Classes & Major Components)")
        for clazz in all_components:
            lines.extend(_render_class(clazz))
        lines.append("")

    # 3. 解析 Functions / Handlers / Constants
    functions = getattr(module, "functions", [])
    exports = getattr(module, "exports", []) # 🟢 支援 export 導出物件 (如 export default App)
    if functions:
        lines.append("## 模組級函式與事件處理器 (Module-level Functions & Handlers)")
        for func in functions:
            lines.extend(_render_method(func, indent=""))
        for exp in exports:
            exp_name = getattr(exp, "name", str(exp))
            lines.append(f"- `export`: {exp_name}")
        lines.append("")

    return "\n".join(lines)