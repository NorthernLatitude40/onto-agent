"""
判斷字串是否為回文 (Palindrome)，忽略大小寫和非字母數字字元（保留數字與字母）。
"""

def is_palindrome(s: str) -> bool:
    """
    判斷字串是否為回文 (Palindrome)，忽略大小寫和非字母數字字元。
    """
    cleaned = "".join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]

