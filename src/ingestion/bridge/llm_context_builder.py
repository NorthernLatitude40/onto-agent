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
    ModuleInfo,
    Statement,
    TryStatement,
    WhileStatement,
)


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


def build_llm_context(module: ModuleInfo) -> str:
    """把 ModuleInfo 轉成適合放進 LLM prompt 的結構化摘要文字。"""

    lines: list[str] = [f"# 檔案: {module.filename or '(unknown)'}", ""]

    if module.imports:
        lines.append("## Imports")
        lines.extend(f"- {imp.name}" for imp in module.imports)
        lines.append("")

    if module.classes:
        lines.append("## Classes")
        for clazz in module.classes:
            lines.extend(_render_class(clazz))
        lines.append("")

    if module.functions:
        lines.append("## Module-level Functions")
        for func in module.functions:
            lines.extend(_render_method(func, indent=""))
        lines.append("")

    return "\n".join(lines)
