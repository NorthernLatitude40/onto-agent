"""
用 GitHub App 身份取得一個已認證的 PyGithub client。

跟個人 PAT 不一樣，這裡走的是「App -> Installation token」的認證方式：
- App 用私鑰簽 JWT 證明自己身份
- 再用這個 JWT 換一個限定在某個 installation（也就是某個 repo/org）範圍內的
  installation access token，這個 token 效期短（約 1 小時），PyGithub 內部
  會自動幫你 refresh，不用自己管理。
"""

import os
from github import Github, Auth


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"缺少環境變數 {name}，請檢查 .env（可參考 .env.example）"
        )
    return value


def get_installation_client() -> Github:
    """回傳一個已經用 GitHub App installation 身份認證好的 Github client。"""
    app_id = _require_env("GITHUB_APP_ID")
    private_key_path = _require_env("GITHUB_APP_PRIVATE_KEY_PATH")
    installation_id = int(_require_env("GITHUB_APP_INSTALLATION_ID"))

    with open(private_key_path, "r", encoding="utf-8") as f:
        private_key = f.read()

    app_auth = Auth.AppAuth(app_id, private_key)
    auth = app_auth.get_installation_auth(installation_id)

    return Github(auth=auth)
