"""
設計書 JSON × IR 反查

LLM 產出的「テーブル」「フィールド」欄位常常是概念性命名（例如 raw.json 裡的
"GlobalState"、"primary, backup_1, backup_2"），不會跟程式碼裡的識別符
逐字對應，所以這裡刻意不用嚴格比對，而是「這個詞在整份 IR 裡有沒有
出現過類似的識別符」的模糊命中檢查。

用法：
    warnings = cross_check(design_doc, module)
    for w in warnings:
        print(w)

結果分兩種：
  - "可能為概念性摘要" → 在程式碼中找不到對應識別符，不代表寫錯，
    但值得人工複核（例如摘要自 docstring / prompt 字串裡的內容）。
  - 找得到 → 不會出現在 warnings 裡（沒消息就是好消息）。
"""
from __future__ import annotations

import re

from src.ingestion.ir.model import ModuleInfo
from src.ontology.screen_dict import HeaderSemanticResolver

_header_resolver = HeaderSemanticResolver()


def _normalize(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token.lower())


def _collect_identifiers(module: ModuleInfo) -> set[str]:
    ids: set[str] = set()

    if module.filename:
        ids.add(module.filename)

    for imp in module.imports:
        ids.add(imp.name)
        ids.add(imp.name.split(".")[-1])

    def add_method(method):
        ids.add(method.name)
        for p in method.parameters:
            ids.add(p.name)
            if p.type:
                ids.add(p.type)
        if method.return_type:
            ids.add(method.return_type)

    for clazz in module.classes:
        ids.add(clazz.name)
        for base in clazz.bases:
            ids.add(base)
        for field in clazz.fields:
            ids.add(field.name)
            if field.type:
                ids.add(field.type)
        for method in clazz.methods:
            add_method(method)

    for func in module.functions:
        add_method(func)

    return {_normalize(i) for i in ids if i}


def _tokens(value: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,\s/、]+", value) if t.strip()]


def cross_check(design_doc: dict, module: ModuleInfo) -> list[str]:
    """回傳一份人類可讀的警告清單（不是拋錯，因為概念性摘要本來就常見）。"""

    identifiers = _collect_identifiers(module)
    warnings: list[str] = []

    for item in design_doc.get("items", []):
        # 防呆層：design_doc 正常來源（validate_design_json 驗證過的
        # DesignItem）已經是 canonical key，這裡是 no-op；
        # 若有人直接拿未經驗證的原始 JSON 呼叫 cross_check，
        # 舊式的表頭原文 key（"No"/"項目名称"/"フィールド"）也能對上。
        normalized_item = {
            (_header_resolver.resolve(k) or k): v for k, v in item.items()
        }

        no = normalized_item.get("no")
        name = normalized_item.get("item_name", "")
        field_domain = normalized_item.get("field_name", "")

        unmatched = [
            tok for tok in _tokens(field_domain)
            if _normalize(tok) not in identifiers and _normalize(tok)
        ]

        domain_tokens = _tokens(field_domain)
        if unmatched and domain_tokens and len(unmatched) == len(domain_tokens):

                warnings.append(
                    f"[No.{no}] 「{name}」的栏域「{field_domain}」在程式碼中找不到對應識別符，"
                    f"可能為概念性摘要，建議人工複核"
                )

    return warnings