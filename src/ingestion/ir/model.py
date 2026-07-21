from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# =====================================================
# Base Node
# =====================================================

class Node(BaseModel):
    """所有IR節點的基類"""

    line: Optional[int] = None
    column: Optional[int] = None


# =====================================================
# Statement
# =====================================================

class Statement(Node):
    """所有Statement基類"""
    pass


class AssignStatement(Statement):
    target: str
    value: str


class ReturnStatement(Statement):
    value: Optional[str] = None


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
    exception_type: Optional[str] = None
    name: Optional[str] = None
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
    type: Optional[str] = None


# =====================================================
# Field
# =====================================================

class FieldInfo(Node):
    name: str
    type: Optional[str] = None
    default_value: Optional[str] = None


# =====================================================
# Method
# =====================================================

class MethodInfo(Node):

    name: str

    parameters: list[ParameterInfo] = Field(default_factory=list)

    return_type: Optional[str] = None

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
# Module
# =====================================================

class ModuleInfo(Node):

    filename: Optional[str] = None

    imports: list[ImportInfo] = Field(default_factory=list)

    classes: list[ClassInfo] = Field(default_factory=list)

    functions: list[MethodInfo] = Field(default_factory=list)
