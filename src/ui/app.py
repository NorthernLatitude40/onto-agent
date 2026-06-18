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
            st.write(user_query)
        st.session_state.chat_history.append({"role": "user", "content": user_query})

        # 建立 AI 的對話氣泡
        with st.chat_message("assistant"):
            # 引入 st.spinner 動畫
            with st.spinner("Harness 運行殼調度內核決策中..."):
                try:
                    # 🌟 核心修改點：直接呼叫 Harness 封裝好的簡潔業務接口
                    # 為網頁端分配專屬的 thread_id，與 API 端完全隔絕
                    final_reply = harness.interact(
                        user_message=user_query, thread_id="streamlit_default_user"
                    )

                    # 將純文字結果直接呈現在 UI 上，並寫入歷史紀錄
                    st.write(final_reply)
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": final_reply}
                    )

                except Exception as e:
                    # 容錯處理：後台列印軌跡，前端彈出紅框
                    import traceback

                    print("❌ [Harness 執行階段崩潰] 詳細錯誤軌跡如下：")
                    traceback.print_exc()
                    st.error(f"🛑 駕馭層（Harness）捕獲異常：{str(e)}")
