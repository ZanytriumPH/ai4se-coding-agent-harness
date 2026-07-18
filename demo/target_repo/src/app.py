# 手写核心素材（§六学术规范）：本文件为手写 mini 目标仓库的实现，非第三方代码。
import os  # F401: unused import (lint)
import sys  # F401: unused import (lint)


def login(user: str, password: str) -> int:
    # BUG: 总是返回 401, 测试期望 200
    return 401


def connect_db(dsn):
    # BUG: 引用未安装模块 → ImportError
    import psycopg2  # noqa
    return psycopg2.connect(dsn)


def add(a: int, b: int) -> int:
    # TYPE ERROR: 返回 str, 注解为 int
    return str(a + b)  # type: ignore 故意触发 mypy


def unused_helper():  # F841-ish: 复杂表达式未用 (lint)
    x = 1
    y = 2
    return x  # y 未用 (lint)