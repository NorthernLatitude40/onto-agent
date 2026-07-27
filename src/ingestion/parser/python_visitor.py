from __future__ import annotations

import ast

from src.ingestion.ir.model import (
    AssignStatement,
    CallStatement,
    ClassInfo,
    ExceptHandlerInfo,
    FieldInfo,
    ForStatement,
    IfStatement,
    ImportInfo,
    MethodInfo,
    ModuleInfo,
    ParameterInfo,
    ReturnStatement,
    Statement,
    TryStatement,
    WhileStatement,
)


class PythonVisitor(ast.NodeVisitor):
    """將 Python AST 轉換為語言無關的 IR (ModuleInfo)。"""

    def __init__(self):

        self.module = ModuleInfo()

        self.current_class: ClassInfo | None = None

        self.current_method: MethodInfo | None = None

        # 目前應該把 Statement 塞進哪個 list，支援 if/for/while 的巢狀結構。
        # 進入方法時 push method.body；進入 if/for/while 的子區塊時再 push 對應的 list。
        self._body_stack: list[list[Statement]] = []

    # ------------------------------------------------
    # 內部工具方法
    # ------------------------------------------------

    def _append_statement(self, stmt: Statement) -> None:
        if self._body_stack:
            self._body_stack[-1].append(stmt)

    def _visit_body(self, body: list[ast.stmt], target: list[Statement]) -> None:
        self._body_stack.append(target)
        for stmt in body:
            self.visit(stmt)
        self._body_stack.pop()

    # ------------------------------------------------
    # import os
    # ------------------------------------------------

    def visit_Import(self, node):

        for alias in node.names:

            self.module.imports.append(
                ImportInfo(
                    name=alias.name,
                    line=node.lineno,
                    column=node.col_offset,
                )
            )

    # ------------------------------------------------
    # from pathlib import Path
    # ------------------------------------------------

    def visit_ImportFrom(self, node):

        module = node.module or ""

        for alias in node.names:

            self.module.imports.append(
                ImportInfo(
                    name=f"{module}.{alias.name}",
                    line=node.lineno,
                    column=node.col_offset,
                )
            )

    # ------------------------------------------------
    # class
    # ------------------------------------------------

    def visit_ClassDef(self, node):

        clazz = ClassInfo(
            name=node.name,
            bases=[ast.unparse(base) for base in node.bases],
            line=node.lineno,
            column=node.col_offset,
        )

        self.module.classes.append(clazz)

        previous_class = self.current_class

        self.current_class = clazz

        for stmt in node.body:
            self.visit(stmt)

        self.current_class = previous_class

    # ------------------------------------------------
    # class 層級欄位: name: type / name: type = value
    # ------------------------------------------------

    def visit_AnnAssign(self, node):

        if self.current_method is not None:
            # 方法內的型別註記賦值，視為一般 Assign 處理
            target = ast.unparse(node.target)
            value = ast.unparse(node.value) if node.value else ""
            self._append_statement(
                AssignStatement(
                    target=target,
                    value=value,
                    line=node.lineno,
                    column=node.col_offset,
                )
            )
            return

        if self.current_class is not None and isinstance(node.target, ast.Name):
            self.current_class.fields.append(
                FieldInfo(
                    name=node.target.id,
                    type=ast.unparse(node.annotation),
                    line=node.lineno,
                    column=node.col_offset,
                )
            )

    # ------------------------------------------------
    # function / async function
    # ------------------------------------------------

    def visit_FunctionDef(self, node):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node)

    def _handle_function(self, node):

        # 巢狀函式（例如某個 method 內部又 def 了一個 closure）用類似
        # Python __qualname__ 的命名方式標記，避免被誤判成 class 真正的方法。
        name = node.name
        if self.current_method is not None:
            name = f"{self.current_method.name}.<locals>.{node.name}"

        method = MethodInfo(
            name=name,
            line=node.lineno,
            column=node.col_offset,
        )

        # parameters
        for arg in node.args.args:

            parameter = ParameterInfo(
                name=arg.arg,
                line=arg.lineno,
                column=arg.col_offset,
            )

            if arg.annotation:
                parameter.type = ast.unparse(arg.annotation)

            method.parameters.append(parameter)

        # return type
        if node.returns:
            method.return_type = ast.unparse(node.returns)

        if self.current_class is not None:
            self.current_class.methods.append(method)
        else:
            self.module.functions.append(method)

        # save current method / body target
        previous_method = self.current_method
        self.current_method = method

        self._visit_body(node.body, method.body)

        self.current_method = previous_method

    # ------------------------------------------------
    # x = 100
    # ------------------------------------------------

    def visit_Assign(self, node):

        if self.current_method is None:
            return

        target = ast.unparse(node.targets[0])

        value = ast.unparse(node.value)

        self._append_statement(
            AssignStatement(
                target=target,
                value=value,
                line=node.lineno,
                column=node.col_offset,
            )
        )

        # self.x = value → 視為所屬 class 的欄位（以 __init__ 為主要偵測位置）
        if (
            self.current_class is not None
            and self.current_method.name == "__init__"
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "self"
        ):
            field_name = node.targets[0].attr

            if not any(f.name == field_name for f in self.current_class.fields):
                self.current_class.fields.append(
                    FieldInfo(
                        name=field_name,
                        default_value=value,
                        line=node.lineno,
                        column=node.col_offset,
                    )
                )

    # ------------------------------------------------
    # return xxx
    # ------------------------------------------------

    def visit_Return(self, node):

        if self.current_method is None:
            return

        value = None

        if node.value:
            value = ast.unparse(node.value)

        self._append_statement(
            ReturnStatement(
                value=value,
                line=node.lineno,
                column=node.col_offset,
            )
        )

    # ------------------------------------------------
    # print(...) / obj.method(...)
    # ------------------------------------------------

    def visit_Expr(self, node):

        if self.current_method is None:
            return

        if not isinstance(node.value, ast.Call):
            return

        call = node.value

        function = ast.unparse(call.func)

        arguments = [
            ast.unparse(arg)
            for arg in call.args
        ]

        self._append_statement(
            CallStatement(
                function=function,
                arguments=arguments,
                line=node.lineno,
                column=node.col_offset,
            )
        )

    # ------------------------------------------------
    # if / elif / else
    # ------------------------------------------------

    def visit_If(self, node):

        if self.current_method is None:
            return

        stmt = IfStatement(
            condition=ast.unparse(node.test),
            line=node.lineno,
            column=node.col_offset,
        )

        self._append_statement(stmt)

        self._visit_body(node.body, stmt.body)
        self._visit_body(node.orelse, stmt.else_body)

    # ------------------------------------------------
    # for
    # ------------------------------------------------

    def visit_For(self, node):
        self._handle_for(node)

    def visit_AsyncFor(self, node):
        self._handle_for(node)

    def _handle_for(self, node):

        if self.current_method is None:
            return

        stmt = ForStatement(
            target=ast.unparse(node.target),
            iterable=ast.unparse(node.iter),
            line=node.lineno,
            column=node.col_offset,
        )

        self._append_statement(stmt)

        self._visit_body(node.body, stmt.body)

    # ------------------------------------------------
    # while
    # ------------------------------------------------

    def visit_While(self, node):

        if self.current_method is None:
            return

        stmt = WhileStatement(
            condition=ast.unparse(node.test),
            line=node.lineno,
            column=node.col_offset,
        )

        self._append_statement(stmt)

        self._visit_body(node.body, stmt.body)

    # ------------------------------------------------
    # try / except / finally
    # ------------------------------------------------

    def visit_Try(self, node):
        self._handle_try(node)

    def visit_TryStar(self, node):  # Python 3.11+ except*
        self._handle_try(node)

    def _handle_try(self, node):

        if self.current_method is None:
            return

        stmt = TryStatement(line=node.lineno, column=node.col_offset)

        self._append_statement(stmt)

        self._visit_body(node.body, stmt.body)

        for handler in node.handlers:
            handler_info = ExceptHandlerInfo(
                exception_type=ast.unparse(handler.type) if handler.type else None,
                name=handler.name,
                line=handler.lineno,
                column=handler.col_offset,
            )
            self._visit_body(handler.body, handler_info.body)
            stmt.handlers.append(handler_info)

        # node.orelse (try...else) 目前併入 body 之後不特別區分，多數情況少見
        self._visit_body(node.finalbody, stmt.finally_body)
