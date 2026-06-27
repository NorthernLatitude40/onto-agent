import streamlit as st
import traceback


def run_ui(harness):
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
                    # 🌟 1. 呼叫我們封裝好的「同步跨執行緒流式接口」取得生成器
                    response_stream = harness.interact_stream_sync(
                        user_message=user_query, thread_id="streamlit_default_user"
                    )

                    # 💡 新增：自定義過濾生成器，只提取真正的純文字內容
                    def text_cleaner_stream(stream):
                        import json

                        for chunk in stream:
                            # 確保 chunk 是字串型態
                            chunk_str = str(chunk).strip()

                            # 1. 跳過空白或非結構化的雜訊
                            if not chunk_str:
                                continue

                            # 2. 嘗試解析是否為符合格式的 JSON
                            try:
                                # 處理可能帶有外層括號的 JSON 陣列或物件
                                data = json.loads(chunk_str)

                                # 如果是列表型態且第一個元素含有 text 欄位
                                if isinstance(data, list) and len(data) > 0:
                                    item = data[0]
                                    if isinstance(item, dict) and "text" in item:
                                        # 排除帶有 "extras" 或 "signature" 的簽章區塊，避免雜訊
                                        if "extras" in item:
                                            continue
                                        yield item["text"]

                                # 如果是字典型態且含有 text 欄位
                                elif isinstance(data, dict) and "text" in data:
                                    if "extras" in data:
                                        continue
                                    yield data["text"]

                            except json.JSONDecodeError:
                                # 如果不是標準 JSON（代表模型已經開始輸出純文字），就直接噴出
                                yield chunk_str

                    # 🌟 2. 將乾淨的生成器丟給 Streamlit 官方的原生流式組件
                    friendly_text = st.write_stream(
                        text_cleaner_stream(response_stream)
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
