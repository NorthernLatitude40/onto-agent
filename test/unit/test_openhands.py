import subprocess
from collections.abc import Sequence
from pathlib import Path

from pydantic import Field

from openhands.sdk import (
    LLM,
    Action,
    Agent,
    Conversation,
    Observation,
    TextContent,
    Tool,
    ToolDefinition,
)
from openhands.sdk.tool import ToolExecutor, register_tool

# --- 1. 定義 write_file 工具 ---


class WriteFileAction(Action):
    filename: str = Field(description="檔案名稱 (例如 fibonacci.py)")
    content: str = Field(description="檔案的完整內容")


class WriteFileObservation(Observation):
    message: str = ""

    @property
    def to_llm_content(self) -> Sequence[TextContent]:
        return [TextContent(text=self.message)]


class WriteFileExecutor(ToolExecutor[WriteFileAction, WriteFileObservation]):
    def __call__(
        self, action: WriteFileAction, conversation=None
    ) -> WriteFileObservation:
        workspace = Path("./workspace").resolve()
        workspace.mkdir(exist_ok=True)
        file_path = workspace / action.filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(action.content)

        return WriteFileObservation(message=f"✅ 成功寫入檔案：{file_path}")


class WriteFileTool(ToolDefinition[WriteFileAction, WriteFileObservation]):
    """寫入內容到工作區的檔案中。"""

    @classmethod
    def create(cls, conv_state=None) -> Sequence["WriteFileTool"]:
        return [
            cls(
                name="write_file",
                description=(
                    "寫入內容到工作區的檔案中。\n"
                    "Args:\n"
                    "  filename: 檔案名稱 (例如 fibonacci.py)\n"
                    "  content: 檔案的完整內容"
                ),
                action_type=WriteFileAction,
                observation_type=WriteFileObservation,
                executor=WriteFileExecutor(),
            )
        ]


# --- 2. 定義 run_bash 工具 ---


class RunBashAction(Action):
    command: str = Field(
        description="要執行的 Terminal 指令 (例如 python fibonacci.py)"
    )


class RunBashObservation(Observation):
    output: str = ""

    @property
    def to_llm_content(self) -> Sequence[TextContent]:
        return [TextContent(text=self.output)]


class RunBashExecutor(ToolExecutor[RunBashAction, RunBashObservation]):
    def __call__(
        self, action: RunBashAction, conversation=None
    ) -> RunBashObservation:
        workspace = Path("./workspace").resolve()
        workspace.mkdir(exist_ok=True)

        result = subprocess.run(
            action.command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
        )

        output = ""
        if result.stdout:
            output += f"【STDOUT】:\n{result.stdout}\n"
        if result.stderr:
            output += f"【STDERR】:\n{result.stderr}\n"
        if result.returncode != 0:
            output += f"\n❌ 命令執行失敗，退出碼: {result.returncode}"
        else:
            output += "\n✅ 命令執行成功！"

        return RunBashObservation(output=output)


class RunBashTool(ToolDefinition[RunBashAction, RunBashObservation]):
    """在工作區目錄下執行 Bash 命令並返回結果。"""

    @classmethod
    def create(cls, conv_state=None) -> Sequence["RunBashTool"]:
        return [
            cls(
                name="run_bash",
                description=(
                    "在工作區目錄下執行 Bash 命令並返回結果。\n"
                    "Args:\n"
                    "  command: 要執行的 Terminal 指令 (例如 python fibonacci.py)"
                ),
                action_type=RunBashAction,
                observation_type=RunBashObservation,
                executor=RunBashExecutor(),
            )
        ]


# --- 3. 主流程邏輯 ---


def main():
    # ------------------------------------------------------------------
    # LLM 設定：使用 openai/ 前綴對齊 LM Studio 相容介面
    # ------------------------------------------------------------------
    llm = LLM(
        usage_id="agent",
        model="openai/qwen/qwen2.5-coder-7b",  # 使用 openai/ 前綴
        base_url="http://192.168.5.25:1234/v1",  # LM Studio Endpoint
        api_key="lm-studio",
        timeout=300,  # 提高超時限制至 300 秒，避免 Prefill 階段觸發 408 Timeout
        max_retries=1,
    )

    # 簡化 Prompt，防止 Prefill 時計算太久
    system_prompt = (
        "You are an active Autonomous Software Engineer.\n"
        "You MUST use the provided tools (`write_file` and `run_bash`) to finish the task.\n"
        "1. First write the Python script using `write_file`.\n"
        "2. Then run the script using `run_bash`.\n"
        "3. If `run_bash` returns an error, fix the code using `write_file` and re-run."
    )

    # 註冊自訂工具
    register_tool("write_file", WriteFileTool)
    register_tool("run_bash", RunBashTool)

    agent = Agent(
        llm=llm,
        tools=[Tool(name="write_file"), Tool(name="run_bash")],
        system_prompt=system_prompt,
    )

    workspace_dir = Path("./workspace").resolve()
    workspace_dir.mkdir(exist_ok=True)

    conversation = Conversation(agent=agent, workspace=workspace_dir)

    task = (
        "請撰寫一個 Python 腳本計算斐波那契數列，存為 fibonacci.py，"
        "並使用 run_bash 執行該腳本，確認輸出無錯。"
    )
    print("🚀 開始執行自進化 Agent 任務 (LM Studio)...")

    conversation.send_message(task)
    conversation.run()

    print("✅ 任務執行完成！請檢查 ./workspace/fibonacci.py 檔案。")


if __name__ == "__main__":
    main()