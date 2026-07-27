import json

import requests
import streamlit as st


def run_ui(harness=None):
    """
    負責 Streamlit 介面渲染。
    支援檔案上傳組件：先上傳至獨立接口取得路徑，對話時一併帶給後端。
    """
    st.set_page_config(page_title="官方智慧售票 Agent (RAG+MCP網路版)", page_icon="🎫")
    st.title("🎫 官方智慧售票 Agent")
    st.caption("🚀 實戰：外掛 AnythingLLM RAG ＋ 本地 MySQL MCP ＋ 獨立檔案上傳通道")

    # ================= 1. 初始化 Streamlit 內建的聊天歷史記憶庫 =================
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "您好！我已經成功外掛了 AnythingLLM 知識庫與網路版 MySQL 資料庫。您可以直接上傳程式碼/文件，然後進行提問！",
            }
        ]

    # 追蹤當前上傳的檔案路徑狀態
    if "uploaded_file_path" not in st.session_state:
        st.session_state.uploaded_file_path = None

    # ================= 1.5 側邊欄或頂部：檔案上傳組件 (0 Token 獨立通道) =================
    with st.sidebar:
        st.header("📂 程式碼與文件上傳")
        uploaded_file = st.file_uploader("上傳要分析的專案檔案", type=["py", "txt", "zip", "json", "md", "tsx"])
        
        if (
            uploaded_file is not None
            and st.session_state.get("last_uploaded_name") != uploaded_file.name
        ):
                with st.spinner("正在上傳檔案至伺服器指定路徑... (0 Token)"):
                    try:
                        UPLOAD_API_URL = "http://127.0.0.1:8000/api/v1/upload"  # 你的獨立上傳接口
                        
                        # 將 streamlit 的上傳檔案封裝並透過 multipart/form-data 發送
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        response = requests.post(UPLOAD_API_URL, files=files, timeout=60)
                        response.raise_for_status()
                        
                        result = response.json()
                        # 將後端回傳的伺服器實體路徑存入 session_state
                        st.session_state.uploaded_file_path = result.get("file_path")
                        st.session_state.last_uploaded_name = uploaded_file.name
                        
                        st.success(f"檔案上傳成功！\n路徑: {st.session_state.uploaded_file_path}")
                    except (RuntimeError, OSError) as e:
                        st.error(f"檔案上傳失敗: {e!s}")

        if st.session_state.uploaded_file_path:
            st.info(f"📌 當前綁定檔案路徑：\n`{st.session_state.uploaded_file_path}`")

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
        with st.chat_message("assistant"), st.spinner("Harness 運行殼調度內核決策中..."):
                try:
                    API_URL = "http://127.0.0.1:8000/api/v1/chat"
                    
                    # 💡 將聊天 Prompt 與剛剛上傳得到的檔案路徑一同打包傳送給後端
                    payload = {
                        "user_id": "streamlit_default_user",
                        "message": user_query,
                        "file_path": st.session_state.uploaded_file_path  # 夾帶路徑給後端/Agent 呼叫 Tool 使用
                    }

                    response_stream = requests.post(
                        API_URL,
                        json=payload,
                        stream=True, 
                        timeout=300,
                    )
                    response_stream.raise_for_status()

                    # 自定義過濾生成器，只提取真正的純文字內容
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

                    # 將乾淨的生成器丟給 Streamlit 官方的原生流式組件
                    friendly_text = st.write_stream(
                        sse_stream(response_stream)
                    )

                    # 將最終生成完畢的完整純文字寫入歷史紀錄
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": friendly_text}
                    )

                except (RuntimeError, OSError) as e:
                    import traceback
                    print("❌ [Harness 執行階段崩潰] 詳細錯誤軌跡如下：")
                    traceback.print_exc()
                    st.error(f"🛑 駕馭層（Harness）捕獲異常：{e!s}")