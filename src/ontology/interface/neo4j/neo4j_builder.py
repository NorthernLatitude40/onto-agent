
import pandas as pd

from src.ontology.interface.ontology.output_contract import MappingRule


class Neo4jBuilder:

    def __init__(self, driver):
        self.driver = driver

    def build_from_rules(self, df: pd.DataFrame, mapping_rules: list[MappingRule]):
        """真正負責和 Neo4j 溝通的血肉之軀"""
        if not mapping_rules:
            return

        raw_rule = mapping_rules[0]

        # 統一轉為純 dict
        if hasattr(raw_rule, "model_dump"):
            rule = raw_rule.model_dump()
        elif hasattr(raw_rule, "dict"):
            rule = raw_rule.dict()
        elif isinstance(raw_rule, dict):
            rule = raw_rule
        else:
            return

        nodes = rule.get("map_to_node", [])
        edges = rule.get("map_to_edge", [])

        # =======================================================
        # 【修正點 1】對應新欄位：concept_id 與 primary_key
        # =======================================================
        label_to_key = {}
        if nodes:
            for n in nodes:
                n_dict = (
                    n.model_dump()
                    if hasattr(n, "model_dump")
                    else (n.dict() if hasattr(n, "dict") else n)
                )
                # 配合 LLM 新格式：改拿 concept_id 與 primary_key
                lbl = n_dict.get("concept_id")
                prop = n_dict.get("primary_key")
                if lbl and prop:
                    label_to_key[lbl] = prop

        with self.driver.session() as session:
            for _, row in df.iterrows():

                # ==========================================
                # 1. 寫入節點
                # ==========================================
                if nodes:
                    for node_rule in nodes:
                        n_dict = (
                            node_rule.model_dump()
                            if hasattr(node_rule, "model_dump")
                            else (
                                node_rule.dict()
                                if hasattr(node_rule, "dict")
                                else node_rule
                            )
                        )

                        # 配合 LLM 新格式
                        label = n_dict.get("concept_id")
                        prop_key = n_dict.get("primary_key")

                        if not label or not prop_key or prop_key not in row:
                            continue

                        val = str(row[prop_key])
                        # 刪除或註釋掉舊的動態切割寫法
                        # uri = f"http://example.org/{label.split('__')[-1]}/{val}"

                        # 直接寫死符合你 .ttl 檔案定義的 ontology 命名空間
                        uri = f"http://example.org/ontology/{val}"

                        cypher = f"""
                        MERGE (n:Resource {{uri: $uri}})
                        SET n:{label}, n.{prop_key} = $val, n.rdfs__label = $val
                        """
                        session.run(cypher, uri=uri, val=val)

                # ==========================================
                # 2. 寫入關係
                # ==========================================
                if edges:
                    for edge_rule in edges:
                        e_dict = (
                            edge_rule.model_dump()
                            if hasattr(edge_rule, "model_dump")
                            else (
                                edge_rule.dict()
                                if hasattr(edge_rule, "dict")
                                else edge_rule
                            )
                        )

                        # =======================================================
                        # 【修正點 2】配合 LLM 關係格式：relationship_id, source_key, target_key
                        # =======================================================
                        edge_type = e_dict.get("relationship_id")  # ns0__bought
                        source_col = e_dict.get("source_key")  # customer_id
                        target_col = e_dict.get("target_key")  # product_id
                        properties_raw = e_dict.get("properties", [])

                        # 處理 properties 可能是 dict 或是 list 的狀況
                        if isinstance(properties_raw, dict):
                            properties = list(properties_raw.keys())
                        else:
                            properties = properties_raw

                        # 找出對應的 Label 名稱
                        # 反向查找：給予欄位名(customer_id)，找到對應 Label(ns0__VIPCustomer)
                        from_label = next(
                            (k for k, v in label_to_key.items() if v == source_col),
                            None,
                        )
                        to_label = next(
                            (k for k, v in label_to_key.items() if v == target_col),
                            None,
                        )

                        if from_label and to_label:
                            # 直接改成與本體論空間一致的路徑
                            from_uri = (
                                f"http://example.org/ontology/{row[source_col]!s}"
                            )
                            to_uri = (
                                f"http://example.org/ontology/{row[target_col]!s}"
                            )

                            props_dict = {}
                            for p in properties:
                                if p in row:
                                    props_dict[p] = (
                                        row[p].item()
                                        if hasattr(row[p], "item")
                                        else row[p]
                                    )

                            cypher_edge = f"""
                            MATCH (a:Resource {{uri: $from_uri}}), (b:Resource {{uri: $to_uri}})
                            MERGE (a)-[r:{edge_type}]->(b)
                            SET r += $props
                            """
                            session.run(
                                cypher_edge,
                                from_uri=from_uri,
                                to_uri=to_uri,
                                props=props_dict,
                            )
