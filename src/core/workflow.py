from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition, ToolNode


class DynamicGraphCompiler:
    def __init__(self, state_schema):
        self.state_schema = state_schema

    def compile_from_json(self, graph_json, tools_list=None, model=None):
        """
        根據前端傳入的 JSON 結構，動態編譯 LangGraph
        """
        # 1. 初始化圖
        graph = StateGraph(self.state_schema)

        node_type_mapping = {}
        llm_node_id = None  # 紀錄大模型的實體 ID

        # 2. 動態添加節點 (Nodes)
        for node in graph_json.get("nodes", []):
            node_id = node["id"]
            node_type = node["type"]
            node_type_mapping[node_id] = node_type  # 記錄 ID 的類型

            if node_type == "llm":
                llm_node_id = node_id  # 記住這個 ID (例如 node_8kc8m70it)
                # 這裡可以根據 config 動態生成 model，此處簡化為調用自定義方法
                graph.add_node(node_id, model)
            elif node_type == "tool_search":

                # 1. 先用 .get() 安全地拿到 config，如果沒有就默認是一個空字典 {}
                node_config = node.get("config", {})

                # 2. 再從這個 config 字典裡去拿 max_attempts，拿不到就默認是 1
                max_attempts = node_config.get("max_attempts", 1)
                # 這裡動態傳入對應的 tools 列表
                retry_cfg = {
                    "max_attempts": max_attempts,
                    "retry_on": Exception,
                }
                graph.add_node(node_id, tools_list, retry=retry_cfg)
            else:
                # 允許未來擴展其他自定義節點
                pass

        # 3. 動態添加邊 (Edges)
        for edge in graph_json.get("edges", []):
            source = edge["source"]
            target = edge["target"]
            # edge_type = edge.get("type", "direct")

            # 處理起點
            if source == "start_node":
                graph.add_edge(START, target)
                continue

            # 根據連線類型決定是普通邊還是條件邊
            source_type = node_type_mapping.get(source)
            target_type = node_type_mapping.get(target)

            if source_type == "llm" and target_type == "tool_search":
                # LangGraph 內置的工具條件跳轉
                graph.add_conditional_edges(
                    source,
                    tools_condition,
                    path_map={
                        "tools": target,
                        "__end__": "__end__",
                    },  # 💡 關鍵：把 "tools" 對齊到隨機 ID)
                )

                # 2. 🔥 【核心作弊】後端自動幫它補上回連大模型的線！
                # 直接把工具節點 (tools) 硬連回大模型 (source)
                graph.add_edge(target, source)
            else:
                graph.add_edge(source, target)
        # 4. 編譯並返回
        return graph.compile(checkpointer=MemorySaver())

    def _build_model_node(self, config):
        # 根據 UI 配置動態生成 model 調用邏輯
        def model_node(state):
            # 你的模型調用邏輯
            return {"messages": ["AI 回覆"]}

        return model_node
