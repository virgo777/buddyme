---
name: python-patterns
description: 构建健壮、高效且易于维护的 Python 应用程序的 Python 惯用法（Pythonic idioms）、PEP 8 标准、类型提示（Type hints）以及最佳实践。
origin: ECC
---

# Python 开发模式 (Python Development Patterns)

用于构建健壮、高效且易于维护的应用程序的 Python 惯用模式与最佳实践。

## 何时激活

- 编写新的 Python 代码时
- 评审 Python 代码时
- 重构现有的 Python 代码时
- 设计 Python 包（Packages）或模块（Modules）时

## 核心原则

### 1. 可读性至上 (Readability Counts)

Python 优先考虑可读性。代码应当直观且易于理解。

```python
# 推荐：清晰且可读
def get_active_users(users: list[User]) -> list[User]:
    """仅从提供的列表中返回活跃用户。"""
    return [user for user in users if user.is_active]


# 不推荐：虽然精简但令人困惑
def get_active_users(u):
    return [x for x in u if x.a]
```

### 2. 显式优于隐式 (Explicit is Better Than Implicit)

避免使用“魔法”；确保代码的行为清晰透明。

```python
# 推荐：显式配置
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 不推荐：隐藏的副作用
import some_module
some_module.setup()  # 这行代码具体做了什么？
```

### 3. EAFP - 宽恕好过许可 (Easier to Ask Forgiveness Than Permission)

Python 倾向于使用异常处理而非预先检查条件。

```python
# 推荐：EAFP 风格
def get_value(dictionary: dict, key: str) -> Any:
    try:
        return dictionary[key]
    except KeyError:
        return default_value

# 不推荐：LBYL (Look Before You Leap) 风格
def get_value(dictionary: dict, key: str) -> Any:
    if key in dictionary:
        return dictionary[key]
    else:
        return default_value
```

## 类型提示 (Type Hints)

### 基础类型标注

```python
from typing import Optional, List, Dict, Any

def process_user(
    user_id: str,
    data: Dict[str, Any],
    active: bool = True
) -> Optional[User]:
    """处理用户并返回更新后的 User 对象或 None。"""
    if not active:
        return None
    return User(user_id, data)
```

### 现代类型提示 (Python 3.9+)

```python
# Python 3.9+ - 使用内置类型
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Python 3.8 及更早版本 - 使用 typing 模块
from typing import List, Dict

def process_items(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}
```

### 类型别名与 TypeVar

```python
from typing import TypeVar, Union

# 复杂类型的类型别名
JSON = Union[dict[str, Any], list[Any], str, int, float, bool, None]

def parse_json(data: str) -> JSON:
    return json.loads(data)

# 泛型类型
T = TypeVar('T')

def first(items: list[T]) -> T | None:
    """返回第一项，如果列表为空则返回 None。"""
    return items[0] if items else None
```

### 基于协议 (Protocol) 的鸭子类型

```python
from typing import Protocol

class Renderable(Protocol):
    def render(self) -> str:
        """将对象渲染为字符串。"""

def render_all(items: list[Renderable]) -> str:
    """渲染所有实现了 Renderable 协议的项。"""
    return "\n".join(item.render() for item in items)
```

## 错误处理模式

### 特定的异常处理

```python
# 推荐：捕获特定的异常
def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            return Config.from_json(f.read())
    except FileNotFoundError as e:
        raise ConfigError(f"未找到配置文件: {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"配置文件中的 JSON 无效: {path}") from e

# 不推荐：空 except
def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            return Config.from_json(f.read())
    except:
        return None  # 静默失败！
```

### 异常链 (Exception Chaining)

```python
def process_data(data: str) -> Result:
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        # 链接异常以保留回溯信息
        raise ValueError(f"无法解析数据: {data}") from e
```

### 自定义异常层级

```python
class AppError(Exception):
    """所有应用程序错误的基类。"""
    pass

class ValidationError(AppError):
    """当输入验证失败时抛出。"""
    pass

class NotFoundError(AppError):
    """当请求的资源未找到时抛出。"""
    pass

# 用法
def get_user(user_id: str) -> User:
    user = db.find_user(user_id)
    if not user:
        raise NotFoundError(f"未找到用户: {user_id}")
    return user
```

## 上下文管理器 (Context Managers)

### 资源管理

```python
# 推荐：使用上下文管理器
def process_file(path: str) -> str:
    with open(path, 'r') as f:
        return f.read()

# 不推荐：手动资源管理
def process_file(path: str) -> str:
    f = open(path, 'r')
    try:
        return f.read()
    finally:
        f.close()
```

### 自定义上下文管理器

```python
from contextlib import contextmanager

@contextmanager
def timer(name: str):
    """计时代码块的上下文管理器。"""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"{name} 耗时 {elapsed:.4f} 秒")

# 用法
with timer("数据处理"):
    process_large_dataset()
```

### 上下文管理器类

```python
class DatabaseTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.begin_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        return False  # 不要抑制异常

# 用法
with DatabaseTransaction(conn):
    user = conn.create_user(user_data)
    conn.create_profile(user.id, profile_data)
```

## 推导式 (Comprehensions) 与生成器 (Generators)

### 列表推导式 (List Comprehensions)

```python
# 推荐：使用列表推导式进行简单的转换
names = [user.name for user in users if user.is_active]

# 不推荐：手动循环
names = []
for user in users:
    if user.is_active:
        names.append(user.name)

# 复杂的推导式应当展开
# 不推荐：过于复杂
result = [x * 2 for x in items if x > 0 if x % 2 == 0]

# 推荐：使用生成器函数
def filter_and_transform(items: Iterable[int]) -> list[int]:
    result = []
    for x in items:
        if x > 0 and x % 2 == 0:
            result.append(x * 2)
    return result
```

### 生成器表达式 (Generator Expressions)

```python
# 推荐：使用生成器进行惰性求值
total = sum(x * x for x in range(1_000_000))

# 不推荐：创建大型中间列表
total = sum([x * x for x in range(1_000_000)])
```

### 生成器函数

```python
def read_large_file(path: str) -> Iterator[str]:
    """逐行读取大文件。"""
    with open(path) as f:
        for line in f:
            yield line.strip()

# 用法
for line in read_large_file("huge.txt"):
    process(line)
```

## 数据类 (Data Classes) 与具名元组 (Named Tuples)

### 数据类 (Data Classes)

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    """具有自动生成的 __init__、__repr__ 和 __eq__ 的用户实体。"""
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

# 用法
user = User(
    id="123",
    name="Alice",
    email="alice@example.com"
)
```

### 带验证的数据类

```python
@dataclass
class User:
    email: str
    age: int

    def __post_init__(self):
        # 验证邮箱格式
        if "@" not in self.email:
            raise ValueError(f"无效的邮箱: {self.email}")
        # 验证年龄范围
        if self.age < 0 or self.age > 150:
            raise ValueError(f"无效的年龄: {self.age}")
```

### 具名元组 (Named Tuples)

```python
from typing import NamedTuple

class Point(NamedTuple):
    """不可变的 2D 点。"""
    x: float
    y: float

    def distance(self, other: 'Point') -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

# 用法
p1 = Point(0, 0)
p2 = Point(3, 4)
print(p1.distance(p2))  # 5.0
```

## 装饰器 (Decorators)

### 函数装饰器

```python
import functools
import time

def timer(func: Callable) -> Callable:
    """计时函数执行的装饰器。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} 耗时 {elapsed:.4f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)

# slow_function() 打印: slow_function took 1.0012s
```

### 参数化装饰器

```python
def repeat(times: int):
    """多次重复执行函数的装饰器。"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            results = []
            for _ in range(times):
                results.append(func(*args, **kwargs))
            return results
        return wrapper
    return decorator

@repeat(times=3)
def greet(name: str) -> str:
    return f"Hello, {name}!"

# greet("Alice") 返回 ["Hello, Alice!", "Hello, Alice!", "Hello, Alice!"]
```

### 基于类的装饰器

```python
class CountCalls:
    """计算函数调用次数的装饰器。"""
    def __init__(self, func: Callable):
        functools.update_wrapper(self, func)
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"{self.func.__name__} 已被调用 {self.count} 次")
        return self.func(*args, **kwargs)

@CountCalls
def process():
    pass

# 每次调用 process() 都会打印调用计数
```

## 并发模式 (Concurrency Patterns)

### 用于 I/O 密集型任务的多线程 (Threading)

```python
import concurrent.futures
import threading

def fetch_url(url: str) -> str:
    """抓取 URL（I/O 密集型操作）。"""
    import urllib.request
    with urllib.request.urlopen(url) as response:
        return response.read().decode()

def fetch_all_urls(urls: list[str]) -> dict[str, str]:
    """使用线程并发抓取多个 URL。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_url, url): url for url in urls}
        results = {}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as e:
                results[url] = f"Error: {e}"
    return results
```

### 用于 CPU 密集型任务的多进程 (Multiprocessing)

```python
def process_data(data: list[int]) -> int:
    """CPU 密集型计算。"""
    return sum(x ** 2 for x in data)

def process_all(datasets: list[list[int]]) -> list[int]:
    """使用多个进程处理多个数据集。"""
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(process_data, datasets))
    return results
```

### 用于并发 I/O 的 Async/Await

```python
import asyncio

async def fetch_async(url: str) -> str:
    """异步抓取 URL。"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def fetch_all(urls: list[str]) -> dict[str, str]:
    """并发抓取多个 URL。"""
    tasks = [fetch_async(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return dict(zip(urls, results))
```

## 包结构组织 (Package Organization)

### 标准项目布局

```
myproject/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── user.py
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   └── test_models.py
├── pyproject.toml
├── README.md
└── .gitignore
```

### 导入规范

```python
# 推荐：导入顺序 - 标准库、第三方库、本地库
import os
import sys
from pathlib import Path

import requests
from fastapi import FastAPI

from mypackage.models import User
from mypackage.utils import format_name

# 推荐：使用 isort 进行自动导入排序
# pip install isort
```

### 用于包导出的 __init__.py

```python
# mypackage/__init__.py
"""mypackage - 一个 Python 包示例。"""

__version__ = "1.0.0"

# 在包级别导出主要的类/函数
from mypackage.models import User, Post
from mypackage.utils import format_name

__all__ = ["User", "Post", "format_name"]
```

## 内存与性能

### 使用 __slots__ 提高内存效率

```python
# 不推荐：普通类使用 __dict__（占用更多内存）
class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

# 推荐：__slots__ 减少内存使用
class Point:
    __slots__ = ['x', 'y']

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
```

### 用于大数据的生成器

```python
# 不推荐：在内存中返回完整列表
def read_lines(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f]

# 推荐：一次产出一行
def read_lines(path: str) -> Iterator[str]:
    with open(path) as f:
        for line in f:
            yield line.strip()
```

### 避免在循环中进行字符串拼接

```python
# 不推荐：由于字符串不可变性，导致 O(n²) 复杂度
result = ""
for item in items:
    result += str(item)

# 推荐：使用 join 实现 O(n) 复杂度
result = "".join(str(item) for item in items)

# 推荐：使用 StringIO 进行构建
from io import StringIO

buffer = StringIO()
for item in items:
    buffer.write(str(item))
result = buffer.getvalue()
```

## Python 工具链集成

### 常用命令

```bash
# 代码格式化
black .
isort .

# 静态检查 (Linting)
ruff check .
pylint mypackage/

# 类型检查
mypy .

# 测试
pytest --cov=mypackage --cov-report=html

# 安全扫描
bandit -r .

# 依赖管理
pip-audit
safety check
```

### pyproject.toml 配置

```toml
[project]
name = "mypackage"
version = "1.0.0"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.31.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]

[tool.black]
line-length = 88
target-version = ['py39']

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=mypackage --cov-report=term-missing"
```

## 快速参考：Python 惯用法

| 惯用法 | 描述 |
|-------|-------------|
| EAFP | 宽恕好过许可 (Easier to Ask Forgiveness than Permission) |
| 上下文管理器 (Context managers) | 使用 `with` 进行资源管理 |
| 列表推导式 (List comprehensions) | 用于简单的转换 |
| 生成器 (Generators) | 用于惰性求值和大型数据集 |
| 类型提示 (Type hints) | 标注函数签名 |
| 数据类 (Dataclasses) | 用于带有自动生成方法的资源容器 |
| `__slots__` | 用于内存优化 |
| f-strings | 用于字符串格式化 (Python 3.6+) |
| `pathlib.Path` | 用于路径操作 (Python 3.4+) |
| `enumerate` | 在循环中获取索引-元素对 |

## 应避免的反模式 (Anti-Patterns)

```python
# 不推荐：可变默认参数
def append_to(item, items=[]):
    items.append(item)
    return items

# 推荐：使用 None 并创建新列表
def append_to(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items

# 不推荐：使用 type() 检查类型
if type(obj) == list:
    process(obj)

# 推荐：使用 isinstance
if isinstance(obj, list):
    process(obj)

# 不推荐：使用 == 与 None 比较
if value == None:
    process()

# 推荐：使用 is
if value is None:
    process()

# 不推荐：from module import *
from os.path import *

# 推荐：显式导入
from os.path import join, exists

# 不推荐：空 except
try:
    risky_operation()
except:
    pass

# 推荐：特定的异常
try:
    risky_operation()
except SpecificError as e:
    logger.error(f"操作失败: {e}")
```

__记住__：Python 代码应当是可读的、显式的，并遵循“最小惊讶原则”（principle of least surprise）。如有疑虑，请优先考虑清晰度而非技巧性。
