"""
新增內容：請合併進現有的 src/ingestion/ir/model.py

因為原始 model.py 沒有一併提供，這裡把新增的 dataclass 獨立放一個檔案，
方便你直接複製貼上。實際使用時應該把下面三個 class 移到 model.py 裡，
和 ClassInfo / MethodInfo / FieldInfo 放在一起，並在 ModuleInfo 加上
`components` 欄位（見檔案最下方）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PropInfo:
    """React 元件的一個 prop（不論是從解構參數或是 TS interface/type 取得）。"""

    name: str
    type: str | None = None
    required: bool = True
    default_value: str | None = None
    line: int = 0
    column: int = 0


@dataclass
class HookCallInfo:
    """元件內呼叫到的 hook，例如 useState(0) / useEffect(fn, [])。"""

    name: str
    arguments: list[str] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class ComponentInfo:
    """一個 React 元件（function component 或 class component）。"""

    name: str
    kind: str = "function"  # "function" | "class"
    is_default_export: bool = False
    # class component 才會有值，例如 "React.Component" / "Component" / "PureComponent"
    base: str | None = None
    props: list[PropInfo] = field(default_factory=list)
    hooks: list[HookCallInfo] = field(default_factory=list)
    line: int = 0
    column: int = 0


# ------------------------------------------------
# 需要對 ModuleInfo 追加的欄位（貼到既有 ModuleInfo dataclass 定義裡）：
#
#     components: list[ComponentInfo] = field(default_factory=list)
#
# 若 ModuleInfo 原本用的是 list[...] 而不是 field(default_factory=...)，
# 請以現有寫法為準，只要型別是 list[ComponentInfo] 即可。
# ------------------------------------------------
