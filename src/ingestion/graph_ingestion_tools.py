import json
import os
import traceback
from typing import List
import pandas as pd
from pydantic import BaseModel, Field
from src.ingestion.excel_loader import ExcelSchemaDiscoverer
from src.ingestion.interface.ontology.output_contract import MappingRule
from src.ingestion.interface.neo4j.neo4j_builder import Neo4jBuilder


class IngestionInput(BaseModel):
    file_path: str = Field(description="Excel 檔案的實體絕對路徑或相對路徑")
    mapping_rules: List[MappingRule] = Field(
        description="由 Agent 根據 Schema 設計出來的圖映射規則清單"
    )


class GraphIngestionTools:
    """
    專門處理大數據源結構探查與 Neo4j 圖數據搬運的 MCP 工具集類別
    """

    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        # 實例化你寫好的核心寫入引擎
        self.neo4j_builder = Neo4jBuilder(self.driver)
        
        # 🎯 效能優化：建立記憶體快取，Key 為 file_path，Value 為 {sheet_name: DataFrame}
        self._cached_dfs = {}

    def inspect_dataset_schema(self, file_path: str) -> str:
        """
        第一步：探查 Excel 結構。
        優化：在此處讀取 Excel 後直接放入快取，防止第二步重新解析 Excel。
        """
        try:
            # 標準化絕對路徑作為快取的 Key
            abs_path = os.path.abspath(file_path) if not file_path.startswith(".") else os.path.normpath(os.path.join(os.getcwd(), file_path.lstrip("./").lstrip(".")))
            
            print(f"📥 [I/O 優化] 正在預先載入並快取 Excel 數據: {abs_path}")
            # 讀取 Excel 的所有工作表 (None 代表全讀)，並存入快取字典
            self._cached_dfs[abs_path] = pd.read_excel(file_path, sheet_name=None)

            discoverer = ExcelSchemaDiscoverer(file_path)
            datasets = discoverer.discover_all_sheets()

            schema_summary = []
            for ds in datasets:
                schema_summary.append(
                    {
                        "sheet_name": ds.table_name,
                        "dataset_id": ds.dataset_id,
                        "fields": [f.model_dump() for f in ds.schema_fields],
                    }
                )
            return json.dumps(schema_summary, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"讀取 Excel 結構失敗: {str(e)}"

    def execute_graph_ingestion(
        self, file_path: str, mapping_rules: List[MappingRule]
    ) -> str:
        """
        第二步：執行圖匯入。
        職責分離：此處只當調度員提取快取 DataFrame，把真正的寫入髒活交給 Neo4jBuilder。
        """
        print("\n" + "=" * 60)
        print("🚀 [MCP TOOL START] 開始執行圖匯入作業")
        print("=" * 60)

        try:
            # 1. 處理檔案路徑
            if file_path.startswith("."):
                base_path = os.getcwd()
                clean_path = file_path.lstrip("./").lstrip(".")
                file_path = os.path.normpath(os.path.join(base_path, clean_path))
            print(f"📂 [INFO] 目標 Excel 絕對路徑: {file_path}")

            # 2. 印出 Agent 傳進來的參數 Log
            serializable_rules = []
            rule_dict = {}
            for i, rule in enumerate(mapping_rules):
                if hasattr(rule, "model_dump"):
                    rule_dict = rule.model_dump(by_alias=False)
                else:
                    rule_dict = rule
                serializable_rules.append(rule_dict)

            nodes = rule_dict.get("map_to_node")
            edges = rule_dict.get("map_to_edge")

            print(f"📋 [RULE] 檢查工作表: '{rule_dict.get('source_sheet')}'")
            print(f"   └─ 🟢 節點映射 (map_to_node): {f'解析成功 (共 {len(nodes)} 筆)' if nodes else '❌ 警告: 為 Null 或是空值!'}")
            print(f"   └─ 🔵 關係映射 (map_to_edge): {f'解析成功 (共 {len(edges)} 筆)' if edges else '❌ 警告: 為 Null 或是空值!'}")

            # 🚨 核心攔截：如果 Agent 擺爛吐了空規則，直接拒絕空轉！
            if not nodes and not edges:
                raise ValueError("Agent 提供的映射規則完全為空 (Null)，已攔截本次無效寫入！")

            # 寫入本地 Debug 快照
            debug_log_path = "src_ingestion_debug.json"
            with open(debug_log_path, "w", encoding="utf-8") as f:
                json.dump({"file_path": file_path, "mapping_rules": serializable_rules}, f, ensure_ascii=False, indent=2)

            # 3. 🎯 效能優化：嘗試命中記憶體快取
            target_sheet = rule_dict.get('source_sheet', 'Orders')
            if file_path in self._cached_dfs and target_sheet in self._cached_dfs[file_path]:
                print("⚡ [PERF] 成功命中記憶體快取！免除二次讀取 Excel 硬碟開銷。")
                df = self._cached_dfs[file_path][target_sheet]
            else:
                print("⚠️ [CACHE MISS] 未命中快取，重新從硬碟解析 Excel...")
                df = pd.read_excel(file_path, sheet_name=target_sheet)

            # ----------------------------------------------------
            # 4. 🚀 漂亮的職責分離：呼叫獨立的 Builder 寫入 Neo4j
            # ----------------------------------------------------
            print("⚙️ [PROCESS] 正在呼叫 Neo4jBuilder 寫入引擎...")
            
            # 呼叫你封裝好的 Builder 方法，把讀好的 df 和規則丟過去
            self.neo4j_builder.build_from_rules(df=df, mapping_rules=mapping_rules)

            # ----------------------------------------------------

            # 寫入成功後釋放快取記憶體
            if file_path in self._cached_dfs:
                del self._cached_dfs[file_path]
                print("🧹 [CACHE] 寫入完成，已釋放記憶體快取。")

            print("✨ [SUCCESS] 圖匯入作業圓滿成功！")
            print("=" * 60 + "\n")
            return "圖資料匯入成功！已透過 Neo4jBuilder 成功寫入 Neo4j。"

        except Exception as e:
            print("\n" + "💥" * 20)
            print("🚨 [ERROR] 圖匯入作業發生致命錯誤！")
            print(f"錯誤類型: {type(e).__name__}")
            print(f"錯誤訊息: {str(e)}")
            print("-" * 40)
            full_traceback = traceback.format_exc()
            print(full_traceback)
            print("💥" * 20 + "\n")
            return f"執行圖匯入失敗。後端報錯：[{type(e).__name__}] {str(e)}。"