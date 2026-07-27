# core/ontology/ontology.py
"""
變更說明（相對於原版 screen_dict.py）：

1. 修正 HEADER_ONTOLOGY 的別名缺漏 —— 原版對著 template_1.xlsx 的真實表頭
   （見文末 __main__ 自我測試）有 4 欄會解析失敗：
     item_name  缺 "項目名稱"（繁體「稱」，原本只有簡體「称」）
     field_code 缺 "欄目號碼"
     table      缺 "表格"
     field_name 缺 "欄域"
   已補上，並多加了幾個常見同義詞。

2. 用 normalize_text() 取代原本的 `str(x).strip().lower()`：
     - Unicode NFKC 正規化（全形/半形字元統一）
     - 去除所有空白（含全形空格），不只是頭尾 strip
     - 若環境裝了 opencc，額外做繁體 -> 簡體轉換，讓「項目名稱」與「項目名称」
       這類繁簡變體不需要在同義詞表裡各寫一份也能對上
       （沒裝 opencc 也不會壞，只是退化成純字面比對，仍需在同義詞表列出兩種寫法）

3. 新增 SHEET_ONTOLOGY + SheetSemanticResolver，解決 tools.py 裡
   `if target_sheet_name in wb.sheetnames` 寫死分頁名稱的問題，
   與表頭解析共用同一套 normalize_text() 邏輯。

4. HeaderSemanticResolver 新增別名衝突檢查（初始化時就會發現同一個別名被
   兩個 canonical key 同時使用的設定錯誤），以及 resolve_columns() /
   find_header_row() 兩個便利方法，取代 tools.py 裡手動掃描表頭列的邏輯。

BusinessTermResolver 未改動。
"""
import re
import unicodedata
import warnings
from typing import Dict, List, Optional

try:
    import opencc

    _T2S = opencc.OpenCC("t2s.json")
except Exception:  # opencc 未安裝時仍可運作，只是不支援繁簡互轉
    _T2S = None


def normalize_text(text: Optional[str]) -> str:
    """統一的文字歸一化：NFKC、去空白（含全形）、繁體轉簡體、小寫化。"""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = re.sub(r"\s+", "", text)
    text = text.lower()
    if _T2S is not None:
        text = _T2S.convert(text)
    return text


# 1. 欄位標頭同義詞映射（解決 Excel 模板標頭變更問題）
HEADER_ONTOLOGY: Dict[str, List[str]] = {
    "no": ["no", "no.", "項番", "序號", "序号", "id"],
    "item_name": ["項目名称", "項目名稱", "項目名", "項目", "欄位名稱", "label"],
    "category": ["分類", "分类", "種別", "种别", "UI分類", "控制項類型", "component", "type"],
    "required": ["必須", "必须", "必須項目", "必填", "required", "is_required"],
    "field_code": ["桁数", "桁數", "欄目號碼", "栏目号码", "長度", "长度", "length", "max_length", "size"],
    "format": ["フォーマット", "格式", "format", "型", "data type"],
    "table": ["テーブル", "テーブル名", "表格", "資料表", "资料表", "table", "table name", "db_table"],
    "field_name": ["フィールド", "フィールド名", "欄位名", "欄域", "字段", "field", "field name", "db_field", "column"],
    "remarks": ["備考", "备考", "備註", "备注", "說明", "说明", "remarks", "comment"],
}

# 1b. Sheet 名稱同義詞映射（解決 tools.py 寫死分頁名稱的問題）
SHEET_ONTOLOGY: Dict[str, List[str]] = {
    "detail_design_sheet": [
        "画面項目", "畫面項目", "画面项目",
        "详细设计书", "詳細設計書",
        "screen items", "screen_item", "detail design", "detail_design",
    ],
}

# 2. 業務詞條庫（解決 Python 變數名 ➔ Excel 邏輯名稱的自動翻譯/對照）
BUSINESS_TERM_ONTOLOGY: Dict[str, Dict[str, str]] = {
    "order_id": {"logical_name": "注文ID", "category": "TextBox", "format": "AN10"},
    "user_id": {"logical_name": "顧客代碼", "category": "TextBox", "format": "AN8"},
    "created_at": {"logical_name": "建立時間", "category": "DatePicker", "format": "YYYY/MM/DD HH:mm"},
    "status": {"logical_name": "狀態選項", "category": "Dropdown", "format": "CodeList"},
    "page": {"logical_name": "頁碼", "category": "Number", "format": "Integer"},
    "page_size": {"logical_name": "每頁筆數", "category": "Number", "format": "Integer"},
    "access_token": {"logical_name": "身份驗證 Token", "category": "Header", "format": "String"},
    "error_code": {"logical_name": "錯誤代碼", "category": "String", "format": "AN5"},
    "error_message": {"logical_name": "錯誤訊息說明", "category": "String", "format": "String"},
    # UI Component 同義詞對應
    "nodes": {"logical_name": "流程圖節點列表", "category": "Canvas/State", "format": "Array"},
    "edges": {"logical_name": "流程圖連線列表", "category": "Canvas/State", "format": "Array"},
    "onconnect": {"logical_name": "節點連線事件處理", "category": "Event/Function", "format": "Handler"},
    "reactflow": {"logical_name": "主繪圖畫布區域", "category": "UI/Canvas", "format": "Component"},
    "controls": {"logical_name": "畫布縮放控制項", "category": "UI/Button", "format": "Component"},
    "minimap": {"logical_name": "鳥瞰縮圖預覽區", "category": "UI/View", "format": "Component"},
}


class _BaseSemanticResolver:
    """共用的別名索引建置邏輯，HeaderSemanticResolver / SheetSemanticResolver 都基於此。"""

    def __init__(self, ontology: Dict[str, List[str]]):
        self.lookup: Dict[str, str] = {}
        for canonical_key, synonyms in ontology.items():
            for syn in [*synonyms, canonical_key]:
                key = normalize_text(syn)
                if not key:
                    continue
                existing = self.lookup.get(key)
                if existing is not None and existing != canonical_key:
                    raise ValueError(
                        f"Ontology 別名衝突: '{syn}' 同時對應 '{existing}' 與 '{canonical_key}'"
                    )
                self.lookup[key] = canonical_key

    def resolve(self, raw_text: Optional[str]) -> Optional[str]:
        if not raw_text:
            return None
        return self.lookup.get(normalize_text(raw_text))


class HeaderSemanticResolver(_BaseSemanticResolver):
    """語義解析器：自動映射 Excel 表頭欄位。"""

    def __init__(self, ontology: Dict[str, List[str]] = HEADER_ONTOLOGY):
        super().__init__(ontology)

    def resolve_columns(self, header_row: List) -> Dict[str, int]:
        """
        輸入表頭那一列的儲存格值（依欄位順序），
        回傳 {canonical_key: 0-based column index}。
        找不到對應本體的表頭會被跳過並記錄 warning。
        """
        column_map: Dict[str, int] = {}
        unresolved: List[tuple] = []
        for idx, header in enumerate(header_row):
            if header is None or str(header).strip() == "":
                continue
            key = self.resolve(header)
            if key is None:
                unresolved.append((idx, str(header)))
                continue
            if key in column_map:
                warnings.warn(
                    f"表頭 '{header}' 解析成 '{key}'，但該 key 已對應到第 "
                    f"{column_map[key]} 欄，第 {idx} 欄將被忽略"
                )
                continue
            column_map[key] = idx

        if unresolved:
            warnings.warn(
                "以下表頭無法對應到 ontology，請確認是否需要補充別名："
                + ", ".join(f"第{i}欄='{h}'" for i, h in unresolved)
            )
        return column_map

    def find_header_row(
        self, rows: List[List], min_matches: int = 3
    ) -> "tuple[Optional[int], Dict[str, int]]":
        """在整張表裡自動找出辨識出最多欄位的那一列，回傳 (0-based 列索引 or None, column_map)。"""
        best_row_idx: Optional[int] = None
        best_map: Dict[str, int] = {}
        for row_idx, row in enumerate(rows):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                candidate_map = self.resolve_columns(list(row))
            if len(candidate_map) > len(best_map):
                best_map = candidate_map
                best_row_idx = row_idx
        if len(best_map) < min_matches:
            return None, {}
        return best_row_idx, best_map


class SheetSemanticResolver(_BaseSemanticResolver):
    """語義解析器：自動映射 workbook 分頁名稱，取代硬編碼的 sheet 名判斷。"""

    def __init__(self, ontology: Dict[str, List[str]] = SHEET_ONTOLOGY):
        super().__init__(ontology)

    def find_sheet_name(self, sheetnames: List[str]) -> Optional[str]:
        for name in sheetnames:
            if self.resolve(name) is not None:
                return name
        return None

    def get_sheet(self, workbook, default_index: Optional[int] = 0):
        """
        1. 先用別名比對 workbook.sheetnames；
        2. 找不到時，default_index 不是 None 就退回該索引的分頁並發出 warning；
        3. default_index 為 None 時，找不到就丟例外。
        """
        matched_name = self.find_sheet_name(workbook.sheetnames)
        if matched_name is not None:
            return workbook[matched_name]
        if default_index is None:
            raise ValueError(f"找不到可辨識的分頁，現有分頁：{workbook.sheetnames}")
        warnings.warn(
            f"找不到可辨識的分頁（現有分頁：{workbook.sheetnames}），"
            f"退回使用第 {default_index} 個分頁；建議確認分頁名稱或補充 SHEET_ONTOLOGY"
        )
        return workbook.worksheets[default_index]


class BusinessTermResolver:
    """業務詞條推導器：根據 Python 變數名自動補全設計書特徵"""

    def __init__(self, ontology=BUSINESS_TERM_ONTOLOGY):
        self.ontology = ontology

    def enrich_field_info(self, py_field_name: str) -> dict:
        """根據 Python 變數名反推設計書中的標籤與格式"""
        clean_name = py_field_name.lower()
        if clean_name in self.ontology:
            return self.ontology[clean_name]

        # 預設通用推導邏輯 (Fallback Policy)
        return {
            "logical_name": py_field_name,
            "category": "TextBox",
            "format": "String",
        }


if __name__ == "__main__":
    # 自我測試：重現 template_1.xlsx 的真實表頭，確認原本會失敗的 4 欄現在都能解析
    resolver = HeaderSemanticResolver()
    real_header = ["No", "項目名稱", "分類", "必須", "欄目號碼", "格式", "表格", None, "欄域", "備考"]
    for h in real_header:
        print(repr(h), "->", resolver.resolve(h))

    print("column_map:", resolver.resolve_columns(real_header))

    sheet_resolver = SheetSemanticResolver()
    print("sheet:", sheet_resolver.find_sheet_name(["详细设计书"]))
