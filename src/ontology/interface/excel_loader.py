import pandas as pd
import uuid
from typing import List
from ontology.interface.dataset import TableDataset, DataFieldSchema, SourceType


class ExcelSchemaDiscoverer:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.excel_file = pd.ExcelFile(file_path)

    def _map_type(self, pandas_dtype: str) -> str:
        """將 Pandas 型態映射到系統統一的資料型態"""
        dtype_str = str(pandas_dtype).lower()
        if "int" in dtype_str:
            return "INTEGER"
        elif "float" in dtype_str:
            return "FLOAT"
        elif "datetime" in dtype_str:
            return "DATETIME"
        elif "bool" in dtype_str:
            return "BOOLEAN"
        else:
            return "STRING"

    def discover_all_sheets(self) -> List[TableDataset]:
        """掃描 Excel 所有 Sheet，並轉換成統一的 Dataset JSON 格式"""
        datasets = []
        source_id = f"src_{uuid.uuid4().hex[:8]}"

        for sheet_name in self.excel_file.sheet_names:
            # 讀取前 100 行來推導 Schema 即可，節省記憶體
            df = pd.read_excel(self.file_path, sheet_name=sheet_name, nrows=100)

            # 1. 解析結構 (Schema Discovery)
            schema_fields = []
            for col_name, dtype in df.dtypes.items():
                schema_fields.append(
                    DataFieldSchema(
                        name=str(col_name),
                        data_type=self._map_type(dtype),
                        raw_type=str(dtype),
                        is_nullable=True,
                    )
                )

            # 2. 讀取全量數據用於後續寫入
            full_df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            # 處理 NaN 轉為 None，避免 JSON 解析錯誤
            full_df = full_df.where(pd.notnull(full_df), None)
            rows = full_df.to_dict(orient="records")

            # 3. 封裝成統一 Dataset
            datasets.append(
                TableDataset(
                    dataset_id=f"{source_id}_{sheet_name.lower()}",
                    source_type=SourceType.EXCEL,
                    table_name=sheet_name,
                    schema_fields=schema_fields,
                    rows=rows,
                )
            )

        return datasets
