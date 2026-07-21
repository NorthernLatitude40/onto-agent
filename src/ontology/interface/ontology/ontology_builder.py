import os
from openai import OpenAI
from ontology.interface.ontology.input_contract import DatasetSchemaInput
from ontology.interface.ontology.output_contract import OntologyBuilderOutput


class LLMOntologyBuilder:
    def __init__(self, llm_agent_client=None):
        """
        傳入你既有的 Agent LLM 實例。
        如果是 LangGraph / LangChain 的 ChatOpenAI 實例，或自訂的 agent 都可以。
        """
        self.client = llm_agent_client

    def build_ontology_with_llm(
        self, schema_input: DatasetSchemaInput
    ) -> OntologyBuilderOutput:
        """
        將 Dataset Schema 丟給 LLM，自動推導並建構出圖本體與映射契約
        """

        # 建立 Prompt，告訴 LLM 它的角色與任務
        system_prompt = (
            "你是一個資深的圖資料庫專家與知識圖譜架構師。\n"
            "任務：請分析使用者提供的資料表 Schema（欄位名稱與型態），將其設計成適合 Neo4j 的圖模型。\n"
            "你需要決定：\n"
            "1. 哪些欄位應該獨立為『節點 (ConceptNode)』，並標示其 Primary Key。\n"
            "2. 哪些欄位是節點的『屬性 (Properties)』。\n"
            "3. 節點與節點之間存在什麼『關係 (RelationshipEdge)』，以及這些關係如何透過 Excel 欄位進行關聯（對接）。\n"
        )

        user_content = f"請幫我將以下資料表轉換為圖結構契約：\n{schema_input.model_dump_json(indent=2)}"

        # 使用 OpenAI Structured Outputs 功能，強迫回傳符合 Pydantic Model 的 JSON
        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",  # 必須使用支援 Structured Outputs 的模型
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format=OntologyBuilderOutput,  # 直接綁定你的輸出契約！
        )

        # 這裡拿到的直接就是填滿資料的 OntologyBuilderOutput 物件
        ontology_output = completion.choices[0].message.parsed
        return ontology_output
