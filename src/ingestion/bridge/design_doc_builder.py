"""
IR (ModuleInfo) → 設計書 JSON 轉換層

負責把 Parser 產出的語言無關 IR（imports / classes / fields / methods /
functions）轉成 tools.py._build_excel() 看得懂的「設計書」格式：

    {
      "items": [
        {"No": 1, "項目名称": ..., "分類": ..., "必須": ...,
         "桁数": ..., "フォーマット": ..., "テーブル": ..., "フィールド": ..., "備考": ...},
        ...
      ]
    }

這一層的映射規則屬於業務決策，以下是預設規則，可依需求調整
（每個規則都寫成獨立的小函式，方便之後替換）：

  - Class      → 一列，分类="類別 (Class)"
  - Field      → 一列，分类="屬性 (Field)"；型別字串含 Optional/None 時 必须="否"
  - Method     → 一列，分类="方法 (Method)"
  - 模組層級函式 → 一列，分类="函式 (Function)"，表格 用檔名
  - Import     → 一列，分类="依賴 (Import)"（預設關閉，見 include_imports）
"""
from __future__ import annotations

from typing import Optional

from src.ingestion.ir.model import ClassInfo, FieldInfo, MethodInfo, ModuleInfo


def _is_optional(type_str: Optional[str]) -> bool:
    if not type_str:
        return True  # 沒有型別註記，視為未強制要求
    return type_str.startswith("Optional[") or "None" in type_str


def _class_row(no: int, index: int, clazz: ClassInfo) -> dict:
    return {
        "No": no,
        "項目名称": clazz.name,
        "分類": "類別 (Class)",
        "必須": "是",
        "桁数": f"CLASS-{index:03d}",
        "フォーマット": "Class",
        "テーブル": clazz.name,
        "フィールド": ", ".join(f.name for f in clazz.fields),
        "備考": f"共 {len(clazz.methods)} 個方法、{len(clazz.fields)} 個屬性",
    }


def _field_row(no: int, table: str, index: int, field: FieldInfo) -> dict:
    return {
        "No": no,
        "項目名称": field.name,
        "分類": "屬性 (Field)",
        "必須": "否" if _is_optional(field.type) else "是",
        "桁数": f"{table.upper()}-F{index:03d}",
        "フォーマット": field.type or "Any",
        "テーブル": table,
        "フィールド": field.name,
        "備考": "",
    }


def _method_row(no: int, table: str, index: int, method: MethodInfo, prefix: str = "M") -> dict:
    params = [p for p in method.parameters if p.name != "self"]
    param_desc = ", ".join(f"{p.name}:{p.type}" if p.type else p.name for p in params)

    return {
        "No": no,
        "項目名称": method.name,
        "分類": "方法 (Method)" if prefix == "M" else "函式 (Function)",
        "必須": "是",
        "桁数": f"{table.upper()}-{prefix}{index:03d}",
        "フォーマット": method.return_type or "None",
        "テーブル": table,
        "フィールド": ", ".join(p.name for p in params),
        "備考": f"參數: {param_desc}" if param_desc else "",
    }


def _import_row(no: int, index: int, name: str, table: str) -> dict:
    return {
        "No": no,
        "項目名称": name,
        "分類": "依賴 (Import)",
        "必須": "是",
        "桁数": f"IMPORT-{index:03d}",
        "フォーマット": "Module",
        "テーブル": table,
        "フィールド": "",
        "備考": "",
    }


def build_design_doc(module: ModuleInfo, include_imports: bool = False) -> dict:
    """將 ModuleInfo 轉成設計書 JSON（dict），可直接餵給 generate_excel。"""

    table_name = module.filename or "Module"
    rows: list[dict] = []
    no = 1

    if include_imports:
        for i, imp in enumerate(module.imports, start=1):
            rows.append(_import_row(no, i, imp.name, table_name))
            no += 1

    for c_idx, clazz in enumerate(module.classes, start=1):
        rows.append(_class_row(no, c_idx, clazz))
        no += 1

        for f_idx, field in enumerate(clazz.fields, start=1):
            rows.append(_field_row(no, clazz.name, f_idx, field))
            no += 1

        for m_idx, method in enumerate(clazz.methods, start=1):
            rows.append(_method_row(no, clazz.name, m_idx, method, prefix="M"))
            no += 1

    for fn_idx, func in enumerate(module.functions, start=1):
        rows.append(_method_row(no, table_name, fn_idx, func, prefix="F"))
        no += 1

    return {"items": rows}
