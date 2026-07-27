# 新增 React (JSX/TSX) 解析支援

## 新增/修改的檔案

- `src/ingestion/ir/model_react_additions.py` — **需要手動合併**。因為你沒有提供原始的
  `model.py`，這裡把新增的 `PropInfo` / `HookCallInfo` / `ComponentInfo` 三個
  dataclass 放在獨立檔案裡。請把它們搬進既有的 `model.py`（跟 `ClassInfo`、
  `MethodInfo` 放在一起），並在 `ModuleInfo` 上加一個欄位：

  ```python
  components: list[ComponentInfo] = field(default_factory=list)
  ```

- `src/ingestion/parser/react_visitor.py` — 新增，對應 `python_visitor.py`。
- `src/ingestion/parser/react_parser.py` — 新增，對應 `python_parser.py`，用
  `@ParserFactory.register` 自動註冊 `language="react"`, `extensions=[".jsx", ".tsx"]`。
- `base.py` / `factory.py` 完全不需要改動，沿用你原本的架構。

## 安裝依賴

Python 沒有內建 JS/TSX 的 AST，這裡用 tree-sitter 來解析：

```
pip install "tree-sitter==0.21.3" tree-sitter-languages
```

> 注意版本：目前 `tree-sitter-languages` 尚未跟上 tree-sitter 0.22+ 的新 API，
> 混用會直接炸掉（`Language.__init__() takes exactly 1 argument`）。
> 已在 `react_parser.py` 裡加了警告過濾，避免 log 被污染。

## 使用方式（跟 PythonParser 完全一致）

```python
from src.ingestion.parser.factory import ParserFactory
import src.ingestion.parser.react_parser  # 觸發 @ParserFactory.register

parser = ParserFactory.get_by_filename("Greeting.tsx")
module = parser.parse(source_code, filename="Greeting.tsx")

for comp in module.components:
    print(comp.name, comp.kind, comp.is_default_export)
    for prop in comp.props:
        print("  prop:", prop.name, prop.type, "required" if prop.required else "optional")
    for hook in comp.hooks:
        print("  hook:", hook.name, hook.arguments)
```

## 解析範圍（依你選的「結構層級」深度）

會抓到：
- `import` 陳述式（default / named / namespace / side-effect import）
- Function component：`function Foo() {}` 與 `const Foo = () => {}` 兩種寫法
- Class component：`class Foo extends React.Component / Component / PureComponent`
- Props：
  - 解構參數（含預設值）：`function Foo({ title, count = 0 })`
  - TypeScript 型別標註對應到的 `interface` / `type` 定義（`: Props`）
  - 上述兩者會合併：解構拿到預設值資訊，型別拿到型別與 required/optional
- Hook 呼叫：任何符合 `use[A-Z]...` 命名、在元件（或 class component 的
  `render`）內被呼叫到的函式，例如 `useState`、`useEffect`、`React.useMemo`

判斷「這是不是一個元件」的規則：**函式名稱大寫開頭 + 函式主體內某處出現
JSX**（`<Div/>`、`<>...</>`）。純大寫命名但沒回傳 JSX 的工具函式（例如範例
裡的 `helperNotAComponent` 反例）不會被誤判成元件。

## 目前不支援 / 之後可以加深的部分

依你選的範圍（結構層級），以下**沒有**做，跟 `PythonVisitor` 對 Python 做的
完整 if/for/while/try 主體解析不同：
- 元件內部的陳述式（if/for/return/assign）沒有轉成 `Statement` tree
- 自訂 hook 的定義本身（`function useMyHook() {...}`）沒有被當成獨立節點記錄，
  只有「被呼叫」這件事會被記錄成 `HookCallInfo`
- 高階元件（HOC）、`React.memo(...)`、`forwardRef(...)` 包裝的元件目前不會被
  識別為 component
- `.js` / `.ts`（沒有 JSX 語法的純 JS/TS 檔）目前沒有註冊副檔名，可以之後視
  需要加進 `extensions`

如果之後想要「跟 Python 一樣深」（解析元件內部的 if/return/hook 依賴等），
可以直接在 `react_visitor.py` 裡沿用同一套 `_body_stack` 模式繼續往下擴充。
