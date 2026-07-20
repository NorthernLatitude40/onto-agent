import streamlit as st
import traceback
import requests
import json



def run_ui(harness=None):
    """
    負責 Streamlit 介面渲染。
    接收重構後的 AgentWorker 實例，透過純同步流程（sync_invoke）
    將使用者請求安全地投遞到背景獨立執行緒的 Event Loop 中執行。
    """
    st.set_page_config(page_title="官方智慧售票 Agent (RAG+MCP網路版)", page_icon="🎫")
    st.title("🎫 官方智慧售票 Agent")
    st.caption("🚀 實戰：外掛 AnythingLLM RAG ＋ 本地 MySQL MCP (雙 Uvicorn 連線版)")

    # ================= 1. 初始化 Streamlit 內建的聊天歷史記憶庫 =================
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "您好！我已經成功外掛了 AnythingLLM 知識庫與網路版 MySQL 資料庫。請隨時提問客服問題或要求我跑評估測試集。",
            }
        ]

    # ================= 2. 渲染歷史對話訊息 =================
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ================= 3. 處理使用者輸入與同步調用流程 =================
    if user_query := st.chat_input("請輸入您的問題..."):
        # 立即將使用者的輸入渲染在網頁上，並寫入歷史紀錄
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.chat_history.append({"role": "user", "content": user_query})

        # 建立 AI 的對話氣泡
        with st.chat_message("assistant"):
            # 引入 st.spinner 動畫
            with st.spinner("Harness 運行殼調度內核決策中..."):
                try:
                    API_URL = "http://127.0.0.1:8000/api/v1/chat"
                    response_stream = requests.post(
                        API_URL,
                        json={
                            "user_id": "streamlit_default_user",
                            "message": user_query
                        },
                        stream=True, 
                        timeout=300,
                    )
                    response_stream.raise_for_status()

                    # 💡 新增：自定義過濾生成器，只提取真正的純文字內容
                    def sse_stream(response):

                        for line in response.iter_lines(decode_unicode=True):

                            if not line:
                                continue

                            if not line.startswith("data: "):
                                continue

                            data = line[6:]

                            try:
                                event = json.loads(data)

                            except json.JSONDecodeError:
                                yield data
                                continue

                            if event["type"] == "status":
                                st.info(event["content"])

                            elif event["type"] == "token":
                                yield event["content"]

                            elif event["type"] == "tool":
                                st.info(f"🔧 调用了 Tool：{event['name']}")

                            elif event["type"] == "result":
                                st.success(event["path"])

                            elif event["type"] == "error":
                                st.error(event["content"])
                            elif event["type"] == "done":
                                break

                    # 🌟 2. 將乾淨的生成器丟給 Streamlit 官方的原生流式組件
                    friendly_text = st.write_stream(
                        sse_stream(response_stream)
                    )

                    # 🌟 3. 將最終生成完畢的完整純文字寫入歷史紀錄
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": friendly_text}
                    )

                except Exception as e:
                    # 容錯處理：後台列印軌跡，前端彈出紅框
                    import traceback

                    print("❌ [Harness 執行階段崩潰] 詳細錯誤軌跡如下：")
                    traceback.print_exc()
                    st.error(f"🛑 駕馭層（Harness）捕獲異常：{str(e)}")
