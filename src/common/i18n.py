# app/core/i18n.py
from typing import Dict

# 💡 多语言字典：以 错误 Code 为 Key，不同语言为字典
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "USER_SHOP_NOT_BOUND": {
        "zh-CN": "当前用户未绑定任何店铺",
        "en-US": "Current user is not bound to any shop.",
        "ja-JP": "現在のユーザーは店舗に紐付けられていません。",
    },
    "PERMISSION_DENIED": {
        "zh-CN": "您没有权限执行此操作",
        "en-US": "You do not have permission to perform this action.",
        "ja-JP": "この操作を実行する権限がありません。",
    },
    "UNAUTHORIZED": {
        "zh-CN": "未登录或凭证已失效",
        "en-US": "Authentication credentials were not provided or invalid.",
        "ja-JP": "認証情報が未提供か、または無効です。",
    },
    "RESOURCE_NOT_FOUND": {
        "zh-CN": "请求的资源不存在",
        "en-US": "The requested resource was not found.",
        "ja-JP": "要求されたリソースが見つかりません。",
    },
    "BAD_REQUEST": {
        "zh-CN": "错误的请求内容",
        "en-US": "Bad request.",
        "ja-JP": "不正なリクエストです。",
    },
}

TRANSLATIONS.update({
    "WX_CODE_EMPTY": {
        "zh-CN": "微信授权 Code 不能为空",
        "en-US": "WeChat authorization code cannot be empty.",
        "ja-JP": "微信認証コードは空にできません。",
    },
    "WX_SERVICE_UNAVAILABLE": {
        "zh-CN": "微信认证服务通信失败，请稍后重试",
        "en-US": "Failed to communicate with WeChat authentication service. Please try again later.",
        "ja-JP": "微信認証サービスとの通信に失敗しました。後ほど再試行してください。",
    },
    "WX_LOGIN_FAILED": {
        "zh-CN": "微信登录失败或 Code 已失效",
        "en-US": "WeChat login failed or the authorization code is invalid.",
        "ja-JP": "微信ログインに失敗したか、コードが無効です。",
    },
    "WX_OPENID_NOT_FOUND": {
        "zh-CN": "未能获取到用户 OpenID",
        "en-US": "Failed to obtain user OpenID.",
        "ja-JP": "ユーザー OpenID を取得できませんでした。",
    },
})

DEFAULT_LANGUAGE = "en-US"


def get_i18n_message(code: str, accept_language: str | None = None, fallback_detail: str | None = None) -> str:
    """
    根据 Accept-Language 请求头与 错误 Code 自动获取对应语言的翻译文本
    """
    # 1. 简单解析请求头，提取主语言（如 "zh-CN,zh;q=0.9,en;q=0.8" -> "zh-CN"）
    target_lang = DEFAULT_LANGUAGE
    if accept_language:
        # 取第一个语言项
        primary_lang = accept_language.split(",")[0].strip()
        # 兼容简写 (如 'zh' 转换为 'zh-CN', 'en' 转换为 'en-US', 'ja' 转换为 'ja-JP')
        if primary_lang.startswith("zh"):
            target_lang = "zh-CN"
        elif primary_lang.startswith("ja"):
            target_lang = "ja-JP"
        elif primary_lang.startswith("en"):
            target_lang = "en-US"

    # 2. 查找字典
    code_dict = TRANSLATIONS.get(code, {})
    
    # 3. 优先级：字典对应语言 > 字典默认英文 > 传入的 fallback_detail > code 本身
    return code_dict.get(
        target_lang,
        code_dict.get(DEFAULT_LANGUAGE, fallback_detail or code)
    )