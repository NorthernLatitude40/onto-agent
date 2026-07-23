"""
IR (ModuleInfo) → 設計書 JSON 轉換層

變更說明（相對於原版）：
  1. 每個 _xxx_row() 函式改回傳 DesignItem（canonical key：no / item_name /
     category / required / field_code / format / table / field_name /
     remarks / is_group），不再用日文表頭原文（"項目名称"/"桁数"/…）當 dict key。
     這樣 tools.py 端不需要對 JSON key 做任何「猜測式」的別名 resolve，
     ontology（screen_dict.py）只需要負責「Excel 表頭 → canonical key」單向映射。
  2. Class 列現在標記 is_group=True，Excel 匯出時會合併整列、灰底顯示，
     視覺上作為底下 Field/Method 列的區塊標題（呼應 tools.py 既有但過去
     沒有資料來源會觸發的 is_group 分支）。
  3. 接上 BusinessTermResolver：屬性列（Field）如果變數名在
     BUSINESS_TERM_ONTOLOGY 裡有登記（如 order_id/user_id/created_at/status），
     item_name 會顯示登記的業務邏輯名稱（如「注文ID」）、format 也會用登記值；
     沒登記的變數則維持原本用 Python 型別字串當 format 的 fallback 行為。
     這是先前「import 了但沒使用」的 BusinessTermResolver，現在真正接上。

build_design_doc() 的輸出仍是 {"items": [...]}，可直接餵給 generate_excel；
差別只在於每個 item 現在是 canonical key 的 dict（DesignItem.model_dump()）。
"""
from __future__ import annotations

from typing import Optional

from src.ingestion.ir.model import ClassInfo, FieldInfo, MethodInfo, ModuleInfo
from src.ingestion.schema.screen_item import DesignItem
from src.ontology.screen_dict import BusinessTermResolver

_business_resolver = BusinessTermResolver()


def _is_optional(type_str: Optional[str]) -> bool:
    if not type_str:
        return True  # 沒有型別註記，視為未強制要求
    return type_str.startswith("Optional[") or "None" in type_str


def _class_row(no: int, index: int, clazz: ClassInfo) -> DesignItem:
    return DesignItem(
        no=no,
        item_name=clazz.name,
        category="類別 (Class)",
        required="是",
        field_code=f"CLASS-{index:03d}",
        format="Class",
        table=clazz.name,
        field_name=", ".join(f.name for f in clazz.fields),
        remarks=f"共 {len(clazz.methods)} 個方法、{len(clazz.fields)} 個屬性",
        is_group=True,
    )


def _field_row(no: int, table: str, index: int, field: FieldInfo) -> DesignItem:
    # 已知業務詞條（如 order_id/user_id）會給出更貼近業務語意的 item_name/format；
    # 未登記的欄位維持原本行為，用 Python 型別字串當 format。
    enriched = _business_resolver.enrich_field_info(field.name)
    known = field.name.lower() in _business_resolver.ontology

    return DesignItem(
        no=no,
        item_name=enriched["logical_name"] if known else field.name,
        category="屬性 (Field)",
        required="否" if _is_optional(field.type) else "是",
        field_code=f"{table.upper()}-F{index:03d}",
        format=enriched["format"] if known else (field.type or "Any"),
        table=table,
        field_name=field.name,
        remarks="",
    )


def _method_row(no: int, table: str, index: int, method: MethodInfo, prefix: str = "M") -> DesignItem:
    params = [p for p in method.parameters if p.name != "self"]
    param_desc = ", ".join(f"{p.name}:{p.type}" if p.type else p.name for p in params)

    return DesignItem(
        no=no,
        item_name=method.name,
        category="方法 (Method)" if prefix == "M" else "函式 (Function)",
        required="是",
        field_code=f"{table.upper()}-{prefix}{index:03d}",
        format=method.return_type or "None",
        table=table,
        field_name=", ".join(p.name for p in params),
        remarks=f"參數: {param_desc}" if param_desc else "",
    )


def _import_row(no: int, index: int, name: str, table: str) -> DesignItem:
    return DesignItem(
        no=no,
        item_name=name,
        category="依賴 (Import)",
        required="是",
        field_code=f"IMPORT-{index:03d}",
        format="Module",
        table=table,
        field_name="",
        remarks="",
    )


def build_design_doc(module: ModuleInfo, include_imports: bool = False) -> dict:
    """將 ModuleInfo 轉成設計書 JSON（dict），可直接餵給 generate_excel。"""

    table_name = module.filename or "Module"
    rows: list[DesignItem] = []
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

    return {"items": [row.model_dump() for row in rows]}
