import os
from ontology.interface.excel_loader import ExcelSchemaDiscoverer
from ontology.interface.ontology.input_contract import DatasetSchemaInput
from ontology.interface.ontology.ontology_builder import LLMOntologyBuilder

if __name__ == "__main__":
    # 1. 動態取得當前腳本所在的資料夾路徑
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. 自動拼接成絕對路徑 (變成 C:\Users\ww\...\src\ingestion\test_sales_data.xlsx)
    excel_path = os.path.join(current_dir, "test_sales_data.xlsx")

    # 3. 傳入正確的路徑
    discoverer = ExcelSchemaDiscoverer(excel_path)
    datasets = discoverer.discover_all_sheets()

    # 拿第一個 Sheet 來做本體建立
    target_dataset = datasets[0]

    # 2. 準備 Ontology Builder 的輸入
    schema_input = DatasetSchemaInput(
        source_id=target_dataset.dataset_id,
        dataset_name=target_dataset.table_name,
        fields=target_dataset.schema_fields,
    )

    # 3. 送入 Ontology Builder (LLM 構建)
    builder = LLMOntologyBuilder()
    final_contract = builder.build_ontology_with_llm(schema_input)

    # 4. 打印最終產出的契約 JSON
    # 這個 JSON 就包含了優化後的圖結構，可以直接餵給下一階段的 Neo4j Builder
    print(final_contract.model_dump_json(indent=2))
