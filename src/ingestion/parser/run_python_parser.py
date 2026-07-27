"""
多語言 Parser Framework - 使用範例（以 Python 為入口）

執行方式（在專案根目錄下）：
    python -m examples.run_python_parser
"""
import textwrap

# 只要 import 到 python_parser 模組，PythonParser 就會透過
# @ParserFactory.register 自動完成註冊。之後新增 Java/Go/... Parser
# 時只需要比照辦理，上層程式碼完全不用修改。
import src.ingestion.parser.python_parser  # noqa: F401
from src.ingestion.parser.factory import ParserFactory

SOURCE = textwrap.dedent("""
    import os
    import sys

    from pathlib import Path


    class User:

        name: str
        age: int = 0

        def __init__(self, name: str, age: int):
            self.name = name
            self.age = age

        def hello(self, name: str, age: int) -> str:

            x = 100

            if age > 18:
                print(name)
                status = "adult"
            else:
                status = "minor"

            for i in range(3):
                print(i)

            while x > 0:
                x = x - 1

            return name


    def test(x: int):

        y = x + 1

        print(y)

        return y
    """)


def main():
    print("已註冊的語言:", ParserFactory.supported_languages())

    parser = ParserFactory.get_by_language("python")
    # 也可以改用副檔名查找： parser = ParserFactory.get_by_filename("demo.py")

    module = parser.parse(SOURCE, filename="demo.py")

    print(module.model_dump_json(indent=2, exclude_none=True))


if __name__ == "__main__":
    main()
