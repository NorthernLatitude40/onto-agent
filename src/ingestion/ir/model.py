from __future__ import annotations

from pydantic import BaseModel, Field

# =====================================================
# Base Node
# =====================================================

class Node(BaseModel):
    """所有IR節點的基類"""

    line: int | None = None
    column: int | None = None


# =====================================================
# Statement
# =====================================================

class Statement(Node):
    """所有Statement基類"""


class AssignStatement(Statement):
    target: str
    value: str


class ReturnStatement(Statement):
    value: str | None = None


class CallStatement(Statement):
    function: str
    arguments: list[str] = Field(default_factory=list)


class IfStatement(Statement):
    condition: str
    body: list[Statement] = Field(default_factory=list)
    else_body: list[Statement] = Field(default_factory=list)


class ForStatement(Statement):
    target: str
    iterable: str
    body: list[Statement] = Field(default_factory=list)


class WhileStatement(Statement):
    condition: str
    body: list[Statement] = Field(default_factory=list)


class ExceptHandlerInfo(Node):
    exception_type: str | None = None
    name: str | None = None
    body: list[Statement] = Field(default_factory=list)


class TryStatement(Statement):
    body: list[Statement] = Field(default_factory=list)
    handlers: list[ExceptHandlerInfo] = Field(default_factory=list)
    finally_body: list[Statement] = Field(default_factory=list)


# =====================================================
# Import
# =====================================================

class ImportInfo(Node):
    name: str


# =====================================================
# Parameter
# =====================================================

class ParameterInfo(Node):
    name: str
    type: str | None = None


# =====================================================
# Field
# =====================================================

class FieldInfo(Node):
    name: str
    type: str | None = None
    default_value: str | None = None


# =====================================================
# Method
# =====================================================

class MethodInfo(Node):

    name: str

    parameters: list[ParameterInfo] = Field(default_factory=list)

    return_type: str | None = None

    body: list[Statement] = Field(default_factory=list)


# =====================================================
# Class
# =====================================================

class ClassInfo(Node):

    name: str

    bases: list[str] = Field(default_factory=list)

    fields: list[FieldInfo] = Field(default_factory=list)

    methods: list[MethodInfo] = Field(default_factory=list)


# =====================================================
# React Component
# =====================================================

class PropInfo(Node):
    """React 元件的一個 prop（不論是從解構參數或是 TS interface/type 取得）。"""

    name: str
    type: str | None = None
    required: bool = True
    default_value: str | None = None


class HookCallInfo(Node):
    """元件內呼叫到的 hook，例如 useState(0) / useEffect(fn, [])。"""

    name: str
    arguments: list[str] = Field(default_factory=list)


class ComponentInfo(Node):
    """一個 React 元件（function component 或 class component）。"""
    name: str
    kind: str = "function"
    is_default_export: bool = False
    base: str | None = None
    props: list[PropInfo] = Field(default_factory=list)
    hooks: list[HookCallInfo] = Field(default_factory=list)
    
    # 🟢 新增：收集元件內部的 UI 控制項
    ui_fields: list[UIFieldInfo] = Field(default_factory=list)

class UIFieldInfo(Node):
    """React 元件內部渲染的 UI 控制項 (如 input, select, textarea, button 等)"""
    tag: str                        # 例如: "input", "select", "textarea", "button"
    type: str = "text"              # 例如: "text", "checkbox", "select"
    label: str | None = None     # 畫面上的標題/Label (若有)
    value_binding: str | None = None # 綁定的變數或狀態, 例如 "data.prompt"
    placeholder: str | None = None
    options: list[str] = Field(default_factory=list) # 下拉選單選項 (對應 <option>)


# =====================================================
# Module
# =====================================================

class ModuleInfo(Node):
    filename: str | None = None
    imports: list[ImportInfo] = Field(default_factory=list)
    classes: list[ClassInfo] = Field(default_factory=list)
    functions: list[MethodInfo] = Field(default_factory=list)
    components: list[ComponentInfo] = Field(default_factory=list)
    
    # 🟢 建議新增：全域變數 / 常量宣告
    variables: list[AssignStatement] = Field(default_factory=list)
