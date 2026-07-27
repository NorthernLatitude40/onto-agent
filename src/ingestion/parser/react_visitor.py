from __future__ import annotations

import re

from tree_sitter import Node

from src.ingestion.ir.model import (
    ComponentInfo,
    HookCallInfo,
    ImportInfo,
    ModuleInfo,
    PropInfo,
)

# use開頭 + 大寫字母，例如 useState / useEffect / useMyCustomHook
_HOOK_NAME_RE = re.compile(r"^use[A-Z0-9]")

_JSX_NODE_TYPES = {
    "jsx_element",
    "jsx_self_closing_element",
    "jsx_fragment",
}

_CLASS_COMPONENT_BASES = {"Component", "React.Component", "PureComponent", "React.PureComponent"}


class ReactVisitor:
    """將 React (JSX/TSX) 原始碼的 tree-sitter AST 轉換為語言無關的 IR (ModuleInfo)。

    目前只做結構層級的解析：import、function/class component、props、hook 呼叫。
    不像 PythonVisitor 一樣往下解析 if/for/return 等陳述式主體。
    """

    def __init__(self, source: bytes):
        self.source = source
        self.module = ModuleInfo()
        # top-level 的 interface / type alias，用來補齊 props 的型別資訊
        # name -> list[(prop_name, type_text, required)]
        self._type_props: dict[str, list[tuple[str, str | None, bool]]] = {}
        # 記錄透過 `export default Foo;` 額外標記為 default export 的名稱
        self._default_export_names: set[str] = set()

    # ------------------------------------------------
    # 小工具
    # ------------------------------------------------

    def _text(self, node: Node | None) -> str:
        if node is None:
            return ""
        return self.source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    @staticmethod
    def _loc(node: Node) -> tuple[int, int]:
        row, col = node.start_point
        return row + 1, col  # 對齊 ast 的慣例：lineno 1-indexed, col_offset 0-indexed

    def _unwrap_export(self, node: Node) -> tuple[Node, bool]:
        """如果 node 是 export_statement，回傳 (內部的宣告節點, 是否為 default export)。"""
        if node.type != "export_statement":
            return node, False

        is_default = any(self._text(c) == "default" for c in node.children)
        declaration = node.child_by_field_name("declaration")
        if declaration is not None:
            return declaration, is_default
        return node, is_default

    def _contains_jsx(self, node: Node) -> bool:
        if node.type in _JSX_NODE_TYPES:
            return True
        for child in node.children:
            if self._contains_jsx(child):
                return True
        return False

    # ------------------------------------------------
    # 進入點
    # ------------------------------------------------

    def visit(self, root: Node) -> ModuleInfo:
        # 第一遍：先收集 top-level 的 interface / type alias 與 `export default Name;`
        for child in root.children:
            self._collect_type_props(child)
            self._collect_bare_default_export(child)

        # 第二遍：真正產出 import / component
        for child in root.children:
            self._visit_top_level(child)

        return self.module

    # ------------------------------------------------
    # import
    # ------------------------------------------------

    def _visit_top_level(self, node: Node) -> None:
        node, is_default = self._unwrap_export(node)

        if node.type == "import_statement":
            self._visit_import(node)
            return

        if node.type == "function_declaration":
            self._visit_function_component(node, is_default_export=is_default)
            return

        if node.type == "class_declaration":
            self._visit_class_component(node, is_default_export=is_default)
            return

        if node.type in ("lexical_declaration", "variable_declaration"):
            self._visit_variable_declaration(node, is_default_export=is_default)
            return

    def _visit_import(self, node: Node) -> None:
        source_node = node.child_by_field_name("source")
        module = self._text(source_node).strip("'\"")
        line, column = self._loc(node)

        clause = next((c for c in node.children if c.type == "import_clause"), None)
        if clause is None:
            # side-effect import, e.g. import './style.css';
            self.module.imports.append(ImportInfo(name=module, line=line, column=column))
            return

        for part in clause.children:
            if part.type == "identifier":
                # default import: import React from 'react'
                self.module.imports.append(
                    ImportInfo(name=f"{module}.default as {self._text(part)}", line=line, column=column)
                )
            elif part.type == "namespace_import":
                # import * as React from 'react'
                name = self._text(part).split("as")[-1].strip()
                self.module.imports.append(
                    ImportInfo(name=f"{module}.* as {name}", line=line, column=column)
                )
            elif part.type == "named_imports":
                for spec in part.children:
                    if spec.type != "import_specifier":
                        continue
                    imported_name = self._text(spec.child_by_field_name("name"))
                    alias_node = spec.child_by_field_name("alias")
                    if alias_node is not None:
                        self.module.imports.append(
                            ImportInfo(
                                name=f"{module}.{imported_name} as {self._text(alias_node)}",
                                line=line,
                                column=column,
                            )
                        )
                    else:
                        self.module.imports.append(
                            ImportInfo(name=f"{module}.{imported_name}", line=line, column=column)
                        )

    # ------------------------------------------------
    # `export default Foo;` (Foo 定義在別處，例如檔案最下面才 export)
    # ------------------------------------------------

    def _collect_bare_default_export(self, node: Node) -> None:
        if node.type != "export_statement":
            return
        if not any(self._text(c) == "default" for c in node.children):
            return
        declaration = node.child_by_field_name("declaration")
        if declaration is not None and declaration.type == "identifier":
            self._default_export_names.add(self._text(declaration))

    # ------------------------------------------------
    # interface Props { ... } / type Props = { ... }
    # ------------------------------------------------

    def _collect_type_props(self, node: Node) -> None:
        node, _ = self._unwrap_export(node)

        object_type = None
        type_name = None

        if node.type == "interface_declaration":
            type_name = self._text(node.child_by_field_name("name"))
            object_type = node.child_by_field_name("body")
        elif node.type == "type_alias_declaration":
            type_name = self._text(node.child_by_field_name("name"))
            value = node.child_by_field_name("value")
            if value is not None and value.type == "object_type":
                object_type = value

        if type_name is None or object_type is None:
            return

        props: list[tuple[str, str | None, bool]] = []
        for member in object_type.children:
            if member.type != "property_signature":
                continue
            prop_name = self._text(member.child_by_field_name("name"))
            required = not any(self._text(c) == "?" for c in member.children)
            type_annotation = member.child_by_field_name("type")
            type_text = None
            if type_annotation is not None:
                # type_annotation 節點包含開頭的 ":"，把它去掉
                type_text = self._text(type_annotation).lstrip(":").strip()
            props.append((prop_name, type_text, required))

        self._type_props[type_name] = props

    # ------------------------------------------------
    # function Foo(...) { ... }
    # ------------------------------------------------

    def _visit_function_component(self, node: Node, is_default_export: bool) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = self._text(name_node)

        body = node.child_by_field_name("body")
        if not (self._looks_like_component(name, body)):
            return

        parameters = node.child_by_field_name("parameters")
        line, column = self._loc(node)

        component = ComponentInfo(
            name=name,
            kind="function",
            is_default_export=is_default_export or name in self._default_export_names,
            line=line,
            column=column,
        )
        component.props = self._extract_props(parameters)
        component.hooks = self._extract_hooks(body) if body is not None else []

        self.module.components.append(component)

    # ------------------------------------------------
    # const Foo = (...) => { ... } / const Foo = (...) => <jsx/>
    # ------------------------------------------------

    def _visit_variable_declaration(self, node: Node, is_default_export: bool) -> None:
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue

            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            if value_node.type not in ("arrow_function", "function_expression"):
                continue

            name = self._text(name_node)
            body = value_node.child_by_field_name("body")

            if not self._looks_like_component(name, body):
                continue

            parameters = value_node.child_by_field_name("parameters")
            line, column = self._loc(declarator)

            component = ComponentInfo(
                name=name,
                kind="function",
                is_default_export=is_default_export or name in self._default_export_names,
                line=line,
                column=column,
            )
            component.props = self._extract_props(parameters)
            component.hooks = self._extract_hooks(body) if body is not None else []

            self.module.components.append(component)

    # ------------------------------------------------
    # class Foo extends React.Component { ... }
    # ------------------------------------------------

    def _visit_class_component(self, node: Node, is_default_export: bool) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = self._text(name_node)

        heritage = next((c for c in node.children if c.type == "class_heritage"), None)
        base_text = None
        type_args_node = None
        if heritage is not None:
            extends_clause = next((c for c in heritage.children if c.type == "extends_clause"), None)
            if extends_clause is not None:
                base_value = extends_clause.child_by_field_name("value")
                base_text = self._text(base_value)
                type_args_node = extends_clause.child_by_field_name("type_arguments")

        if base_text not in _CLASS_COMPONENT_BASES:
            return

        line, column = self._loc(node)
        component = ComponentInfo(
            name=name,
            kind="class",
            is_default_export=is_default_export or name in self._default_export_names,
            base=base_text,
            line=line,
            column=column,
        )

        # extends React.Component<Props> 的情況，從型別參數取得 props
        if type_args_node is not None:
            for arg in type_args_node.children:
                if arg.type == "type_identifier":
                    component.props = self._props_from_type_name(self._text(arg))
                    break

        body = node.child_by_field_name("body")
        render_body = self._find_render_body(body) if body is not None else None
        component.hooks = self._extract_hooks(render_body) if render_body is not None else []

        self.module.components.append(component)

    @staticmethod
    def _find_render_body(class_body: Node) -> Node | None:
        for member in class_body.children:
            if member.type != "method_definition":
                continue
            name_node = member.child_by_field_name("name")
            if name_node is not None and name_node.text.decode() == "render":
                return member.child_by_field_name("body")
        return None

    # ------------------------------------------------
    # 判斷一個 function/arrow function 是不是 React 元件
    # ------------------------------------------------

    @staticmethod
    def _is_capitalized(name: str) -> bool:
        return bool(name) and name[0].isupper()

    def _looks_like_component(self, name: str, body: Node | None) -> bool:
        if not self._is_capitalized(name):
            return False
        if body is None:
            return False
        # body 可能是 statement_block，也可能是 arrow function 的隱式回傳（直接是 jsx_element）
        return self._contains_jsx(body)

    # ------------------------------------------------
    # props
    # ------------------------------------------------

    def _extract_props(self, parameters: Node | None) -> list[PropInfo]:
        if parameters is None:
            return []

        # 單一參數且沒有括號的箭頭函式，parameters 欄位本身就是 identifier
        if parameters.type == "identifier":
            return []

        params = [
            p
            for p in parameters.children
            if p.type in ("required_parameter", "optional_parameter")
        ]
        if not params:
            return []

        first = params[0]
        pattern = first.child_by_field_name("pattern") or (
            first.children[0] if first.children else None
        )
        type_annotation = first.child_by_field_name("type")

        # Case 1: 解構參數 function Foo({ title, count = 0 }: Props)
        if pattern is not None and pattern.type == "object_pattern":
            props = self._props_from_object_pattern(pattern)

            if type_annotation is not None:
                type_name = self._text(type_annotation).lstrip(":").strip()
                typed_props = self._props_from_type_name(type_name)
                props = self._merge_props(props, typed_props)

            return props

        # Case 2: function Foo(props: Props) —— 沒有解構，只能靠型別標註取得 props 清單
        if type_annotation is not None:
            type_name = self._text(type_annotation).lstrip(":").strip()
            typed_props = self._props_from_type_name(type_name)
            if typed_props:
                return typed_props

        # Case 3: function Foo(props) —— 沒有型別資訊，無法得知細節
        return []

    def _props_from_object_pattern(self, pattern: Node) -> list[PropInfo]:
        props: list[PropInfo] = []
        for item in pattern.children:
            line, column = self._loc(item)

            if item.type == "shorthand_property_identifier_pattern":
                props.append(
                    PropInfo(name=self._text(item), required=True, line=line, column=column)
                )
            elif item.type == "object_assignment_pattern":
                left = item.child_by_field_name("left")
                right = item.child_by_field_name("right")
                props.append(
                    PropInfo(
                        name=self._text(left),
                        required=False,
                        default_value=self._text(right),
                        line=line,
                        column=column,
                    )
                )
            elif item.type == "pair_pattern":
                key = item.child_by_field_name("key")
                props.append(
                    PropInfo(name=self._text(key), required=True, line=line, column=column)
                )
        return props

    def _props_from_type_name(self, type_name: str) -> list[PropInfo]:
        entries = self._type_props.get(type_name)
        if not entries:
            return []
        return [
            PropInfo(name=n, type=t, required=r)
            for n, t, r in entries
        ]

    @staticmethod
    def _merge_props(from_destructure: list[PropInfo], from_type: list[PropInfo]) -> list[PropInfo]:
        """以解構參數（有預設值資訊）為主，補上型別資訊；型別裡多出來的 prop 也加進去。"""
        type_by_name = {p.name: p for p in from_type}
        merged: list[PropInfo] = []
        seen = set()

        for prop in from_destructure:
            typed = type_by_name.get(prop.name)
            if typed is not None:
                prop.type = typed.type
                if typed.required is False:
                    prop.required = False
            merged.append(prop)
            seen.add(prop.name)

        for prop in from_type:
            if prop.name not in seen:
                merged.append(prop)

        return merged

    # ------------------------------------------------
    # hooks: useState(...) / useEffect(...) / React.useMemo(...)
    # ------------------------------------------------

    def _extract_hooks(self, body: Node | None) -> list[HookCallInfo]:
        if body is None:
            return []

        hooks: list[HookCallInfo] = []
        self._walk_for_hooks(body, hooks)
        return hooks

    def _walk_for_hooks(self, node: Node, hooks: list[HookCallInfo]) -> None:
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            hook_name = self._hook_name_from_callee(func)
            if hook_name is not None:
                args_node = node.child_by_field_name("arguments")
                arguments = (
                    [self._text(a) for a in args_node.children if a.type not in ("(", ")", ",")]
                    if args_node is not None
                    else []
                )
                line, column = self._loc(node)
                hooks.append(
                    HookCallInfo(name=hook_name, arguments=arguments, line=line, column=column)
                )

        for child in node.children:
            self._walk_for_hooks(child, hooks)

    def _hook_name_from_callee(self, func: Node | None) -> str | None:
        if func is None:
            return None
        if func.type == "identifier":
            name = self._text(func)
            return name if _HOOK_NAME_RE.match(name) else None
        if func.type == "member_expression":
            prop = func.child_by_field_name("property")
            if prop is not None:
                name = self._text(prop)
                return name if _HOOK_NAME_RE.match(name) else None
        return None

    # 在 ReactVisitor 類別中新增方法：

    def _extract_jsx_ui_fields(self, body: Node | None) -> list[dict]:
        """從元件 Body 中提取 HTML/React UI 控制項（Input, Select, Textarea, Button 等）。"""
        if body is None:
            return []
        
        ui_fields = []
        self._walk_jsx_fields(body, ui_fields)
        return ui_fields

    def _walk_jsx_fields(self, node: Node, ui_fields: list[dict]) -> None:
        if node.type in ("jsx_element", "jsx_self_closing_element"):
            # 取得標籤名稱 (e.g. input, select, textarea, button, Handle, option)
            opening_element = node.child_by_field_name("opening_element") or node
            name_node = opening_element.child_by_field_name("name")
            tag_name = self._text(name_node) if name_node else ""

            # 針對常見 UI 表單元素收集屬性
            if tag_name.lower() in ("input", "select", "textarea", "button"):
                attributes = {}
                # 遍歷 JSX 屬性 (e.g. value={data.prompt}, placeholder="...")
                for child in opening_element.children:
                    if child.type == "jsx_attribute":
                        attr_name_node = child.child_by_field_name("name")
                        attr_val_node = child.child_by_field_name("value")
                        if attr_name_node:
                            attr_name = self._text(attr_name_node)
                            attr_val = self._text(attr_val_node) if attr_val_node else "True"
                            attributes[attr_name] = attr_val.strip("\"'{}")

                line, _col = self._loc(node)
                ui_fields.append({
                    "tag": tag_name,
                    "type": attributes.get("type", tag_name),
                    "value_binding": attributes.get("value", ""),
                    "placeholder": attributes.get("placeholder", ""),
                    "line": line
                })

        for child in node.children:
            self._walk_jsx_fields(child, ui_fields)
