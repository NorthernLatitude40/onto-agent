"""
把 agent 產生的代碼變更提交到 GitHub：
開一個新分支 -> commit（新增或修改檔案都支援）-> 開 PR（不自動 merge，留給 CI / 人工 review 把關）。

也提供 get_file_content，讓 agent 在「修 bug / 改代碼」前，能先讀到 repo 裡
現有檔案的內容，用來組成餵給 LLM 的 prompt。
"""

import re
import time
from dataclasses import dataclass
from typing import List, Optional

from github import GithubException
from github.PullRequest import PullRequest

from .github_app import get_installation_client


@dataclass
class FileChange:
    path: str
    content: str
    commit_message: Optional[str] = None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "change"


def get_file_content(owner: str, repo: str, path: str, ref: str = "main") -> str:
    """
    讀取 repo 裡某個檔案目前的內容，用在「修 bug / 改代碼」流程：
    先讀現有代碼，連同 bug 描述一起餵給 LLM，讓它生成修改後的完整內容。

    :param owner: repo 所屬帳號/組織
    :param repo: repo 名稱
    :param path: 檔案路徑，例如 "src/core/some_module.py"
    :param ref: 要讀哪個分支/commit 上的版本，預設 main
    :raises FileNotFoundError: 該路徑在指定 ref 上不存在
    """
    client = get_installation_client()
    gh_repo = client.get_repo(f"{owner}/{repo}")

    try:
        file_content = gh_repo.get_contents(path, ref=ref)
    except GithubException as e:
        if e.status == 404:
            raise FileNotFoundError(f"{owner}/{repo}@{ref} 找不到檔案: {path}") from e
        raise

    if isinstance(file_content, list):
        raise IsADirectoryError(f"{path} 是資料夾，不是檔案")

    return file_content.decoded_content.decode("utf-8")


def submit_code_change(
    *,
    owner: str,
    repo: str,
    change_id: str,
    files: List[FileChange],
    base_branch: str = "main",
    pr_title: Optional[str] = None,
    pr_body: Optional[str] = None,
) -> PullRequest:
    """
    建分支 -> commit files 裡的每個檔案（新增或修改都支援）-> 開 PR。

    :param owner: repo 所屬帳號/組織
    :param repo: repo 名稱
    :param change_id: 這次變更的識別字（例如工具名稱、或 "fix-xxx-bug"），
                       只用來組分支名跟預設 PR 標題，跟檔案內容無關
    :param files: 要新增/更新的檔案清單。path 若對應到 repo 裡既有的檔案，
                  會自動用 update_file 覆蓋；不存在則用 create_file 新建
    :param base_branch: 從哪個分支切出去
    :param pr_title: PR 標題，不給的話用預設格式
    :param pr_body: PR 內文，不給的話用預設格式
    """
    if not files:
        raise ValueError("files 不能是空 list —— 至少要提交一個檔案")

    client = get_installation_client()
    gh_repo = client.get_repo(f"{owner}/{repo}")

    # 1. 取得 base branch 目前的 commit sha，作為新分支起點
    base_ref = gh_repo.get_git_ref(f"heads/{base_branch}")
    base_sha = base_ref.object.sha

    # 2. 建立新分支（用時間戳確保分支名不重複）
    branch_name = f"agent/{_slugify(change_id)}-{int(time.time())}"
    gh_repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)

    # 3. 逐一 commit 檔案（存在則更新，否則新建 —— 修 bug 走的就是「更新」這條路徑）
    for file_change in files:
        commit_message = file_change.commit_message or f"chore: update {file_change.path}"

        try:
            existing = gh_repo.get_contents(file_change.path, ref=branch_name)
            gh_repo.update_file(
                path=file_change.path,
                message=commit_message,
                content=file_change.content,
                sha=existing.sha,
                branch=branch_name,
            )
        except GithubException as e:
            if e.status == 404:
                gh_repo.create_file(
                    path=file_change.path,
                    message=commit_message,
                    content=file_change.content,
                    branch=branch_name,
                )
            else:
                raise

    # 4. 開 PR（故意不呼叫 merge —— 交給 CI 測試 + 人工 review）
    pr = gh_repo.create_pull(
        title=pr_title or f"[Agent] {change_id}",
        body=pr_body or "此 PR 由 agent 自動產生並已通過本地測試，請 review 後再合併。",
        head=branch_name,
        base=base_branch,
    )

    return pr


# 向下相容別名：舊程式碼裡 import submit_new_tool 的地方不用改，
# 只是底層邏輯其實一直都支援新增跟修改兩種情境。
submit_new_tool = submit_code_change
