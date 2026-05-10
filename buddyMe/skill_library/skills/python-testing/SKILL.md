---
name: python-testing
description: 使用 pytest、TDD 方法论、测试夹具（Fixtures）、模拟（Mocking）、参数化（Parametrization）以及覆盖率要求的 Python 测试策略。
origin: ECC
---

# Python 测试模式（Python Testing Patterns）

使用 pytest、测试驱动开发（TDD）方法论和最佳实践的 Python 应用程序综合测试策略。

## 何时激活

- 编写新的 Python 代码时（遵循 TDD：红、绿、重构）
- 为 Python 项目设计测试套件时
- 审查 Python 测试覆盖率时
- 搭建测试基础设施时

## 核心测试哲学

### 测试驱动开发 (TDD)

始终遵循 TDD 循环：

1. **红（RED）**：为期望的行为编写一个失败的测试
2. **绿（GREEN）**：编写最少的代码使测试通过
3. **重构（REFACTOR）**：在保持测试通过的同时改进代码

```python
# 步骤 1：编写失败的测试 (红)
def test_add_numbers():
    result = add(2, 3)
    assert result == 5

# 步骤 2：编写最简实现 (绿)
def add(a, b):
    return a + b

# 步骤 3：如果需要则进行重构 (重构)
```

### 覆盖率要求

- **目标**：80% 以上的代码覆盖率
- **关键路径**：要求 100% 覆盖率
- 使用 `pytest --cov` 来衡量覆盖率

```bash
pytest --cov=mypackage --cov-report=term-missing --cov-report=html
```

## pytest 基础

### 基本测试结构

```python
import pytest

def test_addition():
    """测试基本的加法。"""
    assert 2 + 2 == 4

def test_string_uppercase():
    """测试字符串转大写。"""
    text = "hello"
    assert text.upper() == "HELLO"

def test_list_append():
    """测试列表追加。"""
    items = [1, 2, 3]
    items.append(4)
    assert 4 in items
    assert len(items) == 4
```

### 断言（Assertions）

```python
# 相等
assert result == expected

# 不等
assert result != unexpected

# 真值性 (Truthiness)
assert result  # 为真 (Truthy)
assert not result  # 为假 (Falsy)
assert result is True  # 严格为 True
assert result is False  # 严格为 False
assert result is None  # 严格为 None

# 成员关系
assert item in collection
assert item not in collection

# 比较
assert result > 0
assert 0 <= result <= 100

# 类型检查
assert isinstance(result, str)

# 异常测试 (推荐方法)
with pytest.raises(ValueError):
    raise ValueError("error message")

# 检查异常消息
with pytest.raises(ValueError, match="invalid input"):
    raise ValueError("invalid input provided")

# 检查异常属性
with pytest.raises(ValueError) as exc_info:
    raise ValueError("error message")
assert str(exc_info.value) == "error message"
```

## 测试夹具 (Fixtures)

### 基本夹具用法

```python
import pytest

@pytest.fixture
def sample_data():
    """提供示例数据的夹具。"""
    return {"name": "Alice", "age": 30}

def test_sample_data(sample_data):
    """使用该夹具进行测试。"""
    assert sample_data["name"] == "Alice"
    assert sample_data["age"] == 30
```

### 带有设置/拆卸 (Setup/Teardown) 的夹具

```python
@pytest.fixture
def database():
    """带有设置和拆卸功能的夹具。"""
    # 设置 (Setup)
    db = Database(":memory:")
    db.create_tables()
    db.insert_test_data()

    yield db  # 提供给测试函数

    # 拆卸 (Teardown)
    db.close()

def test_database_query(database):
    """测试数据库操作。"""
    result = database.query("SELECT * FROM users")
    assert len(result) > 0
```

### 夹具作用域 (Scopes)

```python
# 函数作用域 (默认) - 每个测试运行一次
@pytest.fixture
def temp_file():
    with open("temp.txt", "w") as f:
        yield f
    os.remove("temp.txt")

# 模块作用域 - 每个模块运行一次
@pytest.fixture(scope="module")
def module_db():
    db = Database(":memory:")
    db.create_tables()
    yield db
    db.close()

# 会话作用域 - 整个测试会话运行一次
@pytest.fixture(scope="session")
def shared_resource():
    resource = ExpensiveResource()
    yield resource
    resource.cleanup()
```

### 带有参数的夹具

```python
@pytest.fixture(params=[1, 2, 3])
def number(request):
    """参数化夹具。"""
    return request.param

def test_numbers(number):
    """测试将运行 3 次，每个参数一次。"""
    assert number > 0
```

### 使用多个夹具

```python
@pytest.fixture
def user():
    return User(id=1, name="Alice")

@pytest.fixture
def admin():
    return User(id=2, name="Admin", role="admin")

def test_user_admin_interaction(user, admin):
    """使用多个夹具进行测试。"""
    assert admin.can_manage(user)
```

### 自动使用 (Autouse) 夹具

```python
@pytest.fixture(autouse=True)
def reset_config():
    """在每个测试之前自动运行。"""
    Config.reset()
    yield
    Config.cleanup()

def test_without_fixture_call():
    # reset_config 自动运行
    assert Config.get_setting("debug") is False
```

### 用于共享夹具的 Conftest.py

```python
# tests/conftest.py
import pytest

@pytest.fixture
def client():
    """所有测试共享的夹具。"""
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_headers(client):
    """为 API 测试生成认证头。"""
    response = client.post("/api/login", json={
        "username": "test",
        "password": "test"
    })
    token = response.json["token"]
    return {"Authorization": f"Bearer {token}"}
```

## 参数化 (Parametrization)

### 基本参数化

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("PyThOn", "PYTHON"),
])
def test_uppercase(input, expected):
    """使用不同输入运行 3 次测试。"""
    assert input.upper() == expected
```

### 多个参数

```python
@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (0, 0, 0),
    (-1, 1, 0),
    (100, 200, 300),
])
def test_add(a, b, expected):
    """使用多个输入测试加法。"""
    assert add(a, b) == expected
```

### 使用 ID 进行参数化

```python
@pytest.mark.parametrize("input,expected", [
    ("valid@email.com", True),
    ("invalid", False),
    ("@no-domain.com", False),
], ids=["valid-email", "missing-at", "missing-domain"])
def test_email_validation(input, expected):
    """使用可读的测试 ID 测试电子邮件验证。"""
    assert is_valid_email(input) is expected
```

### 参数化夹具

```python
@pytest.fixture(params=["sqlite", "postgresql", "mysql"])
def db(request):
    """针对多个数据库后端进行测试。"""
    if request.param == "sqlite":
        return Database(":memory:")
    elif request.param == "postgresql":
        return Database("postgresql://localhost/test")
    elif request.param == "mysql":
        return Database("mysql://localhost/test")

def test_database_operations(db):
    """测试将运行 3 次，每个数据库一次。"""
    result = db.query("SELECT 1")
    assert result is not None
```

## 标记 (Markers) 与测试选择

### 自定义标记

```python
# 标记慢速测试
@pytest.mark.slow
def test_slow_operation():
    time.sleep(5)

# 标记集成测试
@pytest.mark.integration
def test_api_integration():
    response = requests.get("https://api.example.com")
    assert response.status_code == 200

# 标记单元测试
@pytest.mark.unit
def test_unit_logic():
    assert calculate(2, 3) == 5
```

### 运行特定测试

```bash
# 仅运行非慢速测试
pytest -m "not slow"

# 仅运行集成测试
pytest -m integration

# 运行集成测试或慢速测试
pytest -m "integration or slow"

# 运行标记为 unit 但不是 slow 的测试
pytest -m "unit and not slow"
```

### 在 pytest.ini 中配置标记

```ini
[pytest]
markers =
    slow: 将测试标记为慢速
    integration: 将测试标记为集成测试
    unit: 将测试标记为单元测试
    django: 将测试标记为需要 Django
```

## 模拟 (Mocking) 与打补丁 (Patching)

### 模拟函数

```python
from unittest.mock import patch, Mock

@patch("mypackage.external_api_call")
def test_with_mock(api_call_mock):
    """使用模拟的外部 API 进行测试。"""
    api_call_mock.return_value = {"status": "success"}

    result = my_function()

    api_call_mock.assert_called_once()
    assert result["status"] == "success"
```

### 模拟返回值

```python
@patch("mypackage.Database.connect")
def test_database_connection(connect_mock):
    """使用模拟的数据库连接进行测试。"""
    connect_mock.return_value = MockConnection()

    db = Database()
    db.connect()

    connect_mock.assert_called_once_with("localhost")
```

### 模拟异常

```python
@patch("mypackage.api_call")
def test_api_error_handling(api_call_mock):
    """使用模拟的异常测试错误处理。"""
    api_call_mock.side_effect = ConnectionError("Network error")

    with pytest.raises(ConnectionError):
        api_call()

    api_call_mock.assert_called_once()
```

### 模拟上下文管理器

```python
@patch("builtins.open", new_callable=mock_open)
def test_file_reading(mock_file):
    """使用模拟的 open 测试文件读取。"""
    mock_file.return_value.read.return_value = "file content"

    result = read_file("test.txt")

    mock_file.assert_called_once_with("test.txt", "r")
    assert result == "file content"
```

### 使用 Autospec

```python
@patch("mypackage.DBConnection", autospec=True)
def test_autospec(db_mock):
    """使用 autospec 捕获 API 误用。"""
    db = db_mock.return_value
    db.query("SELECT * FROM users")

    # 如果 DBConnection 没有 query 方法，这将会失败
    db_mock.assert_called_once()
```

### 模拟类实例

```python
class TestUserService:
    @patch("mypackage.UserRepository")
    def test_create_user(self, repo_mock):
        """使用模拟的仓库测试用户创建。"""
        repo_mock.return_value.save.return_value = User(id=1, name="Alice")

        service = UserService(repo_mock.return_value)
        user = service.create_user(name="Alice")

        assert user.name == "Alice"
        repo_mock.return_value.save.assert_called_once()
```

### 模拟属性

```python
@pytest.fixture
def mock_config():
    """创建一个带有属性的模拟对象。"""
    config = Mock()
    type(config).debug = PropertyMock(return_value=True)
    type(config).api_key = PropertyMock(return_value="test-key")
    return config

def test_with_mock_config(mock_config):
    """使用模拟的配置属性进行测试。"""
    assert mock_config.debug is True
    assert mock_config.api_key == "test-key"
```

## 测试异步代码

### 使用 pytest-asyncio 进行异步测试

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数。"""
    result = await async_add(2, 3)
    assert result == 5

@pytest.mark.asyncio
async def test_async_with_fixture(async_client):
    """配合异步夹具测试异步函数。"""
    response = await async_client.get("/api/users")
    assert response.status_code == 200
```

### 异步夹具

```python
@pytest.fixture
async def async_client():
    """提供异步测试客户端的异步夹具。"""
    app = create_app()
    async with app.test_client() as client:
        yield client

@pytest.mark.asyncio
async def test_api_endpoint(async_client):
    """使用异步夹具进行测试。"""
    response = await async_client.get("/api/data")
    assert response.status_code == 200
```

### 模拟异步函数

```python
@pytest.mark.asyncio
@patch("mypackage.async_api_call")
async def test_async_mock(api_call_mock):
    """使用模拟对象测试异步函数。"""
    api_call_mock.return_value = {"status": "ok"}

    result = await my_async_function()

    api_call_mock.assert_awaited_once()
    assert result["status"] == "ok"
```

## 测试异常

### 测试预期的异常

```python
def test_divide_by_zero():
    """测试除以零会引发 ZeroDivisionError。"""
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

def test_custom_exception():
    """测试带有消息的自定义异常。"""
    with pytest.raises(ValueError, match="invalid input"):
        validate_input("invalid")
```

### 测试异常属性

```python
def test_exception_with_details():
    """测试带有自定义属性的异常。"""
    with pytest.raises(CustomError) as exc_info:
        raise CustomError("error", code=400)

    assert exc_info.value.code == 400
    assert "error" in str(exc_info.value)
```

## 测试副作用

### 测试文件操作

```python
import tempfile
import os

def test_file_processing():
    """使用临时文件测试文件处理。"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("test content")
        temp_path = f.name

    try:
        result = process_file(temp_path)
        assert result == "processed: test content"
    finally:
        os.unlink(temp_path)
```

### 使用 pytest 的 tmp_path 夹具进行测试

```python
def test_with_tmp_path(tmp_path):
    """使用 pytest 内置的临时路径夹具进行测试。"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    result = process_file(str(test_file))
    assert result == "hello world"
    # tmp_path 会被自动清理
```

### 使用 tmpdir 夹具进行测试

```python
def test_with_tmpdir(tmpdir):
    """使用 pytest 的 tmpdir 夹具进行测试。"""
    test_file = tmpdir.join("test.txt")
    test_file.write("data")

    result = process_file(str(test_file))
    assert result == "data"
```

## 测试组织

### 目录结构

```
tests/
├── conftest.py                 # 共享夹具
├── __init__.py
├── unit/                       # 单元测试
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_utils.py
│   └── test_services.py
├── integration/                # 集成测试
│   ├── __init__.py
│   ├── test_api.py
│   └── test_database.py
└── e2e/                        # 端到端测试
    ├── __init__.py
    └── test_user_flow.py
```

### 测试类

```python
class TestUserService:
    """在类中组织相关的测试。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置代码在类中的每个测试之前运行。"""
        self.service = UserService()

    def test_create_user(self):
        """测试用户创建。"""
        user = self.service.create_user("Alice")
        assert user.name == "Alice"

    def test_delete_user(self):
        """测试用户删除。"""
        user = User(id=1, name="Bob")
        self.service.delete_user(user)
        assert not self.service.user_exists(1)
```

## 最佳实践

### 建议做法 (DO)

- **遵循 TDD**：先写测试再写代码（红-绿-重构）
- **单一职责测试**：每个测试应仅验证一个行为
- **使用描述性名称**：例如 `test_user_login_with_invalid_credentials_fails`
- **使用夹具**：通过测试夹具（Fixtures）消除重复
- **模拟外部依赖**：不要依赖外部服务
- **测试边缘情况**：空输入、None 值、边界条件
- **追求 80% 以上的覆盖率**：重点关注关键路径
- **保持测试快速**：使用标记（Marks）分离慢速测试

### 避免做法 (DON'T)

- **不要测试实现细节**：测试行为，而不是内部实现
- **不要在测试中使用复杂的条件逻辑**：保持测试简单
- **不要忽视失败的测试**：所有测试都必须通过
- **不要测试第三方代码**：信任库本身的功能
- **不要在测试之间共享状态**：测试应该是独立的
- **不要在测试中捕获异常**：应使用 `pytest.raises`
- **不要使用 print 语句**：应使用断言和 pytest 输出
- **不要编写过于脆弱的测试**：避免过度具体的模拟（Mocking）

## 常见模式

### 测试 API 端点 (FastAPI/Flask)

```python
@pytest.fixture
def client():
    app = create_app(testing=True)
    return app.test_client()

def test_get_user(client):
    response = client.get("/api/users/1")
    assert response.status_code == 200
    assert response.json["id"] == 1

def test_create_user(client):
    response = client.post("/api/users", json={
        "name": "Alice",
        "email": "alice@example.com"
    })
    assert response.status_code == 201
    assert response.json["name"] == "Alice"
```

### 测试数据库操作

```python
@pytest.fixture
def db_session():
    """创建测试数据库会话。"""
    session = Session(bind=engine)
    session.begin_nested()
    yield session
    session.rollback()
    session.close()

def test_create_user(db_session):
    user = User(name="Alice", email="alice@example.com")
    db_session.add(user)
    db_session.commit()

    retrieved = db_session.query(User).filter_by(name="Alice").first()
    assert retrieved.email == "alice@example.com"
```

### 测试类方法

```python
class TestCalculator:
    @pytest.fixture
    def calculator(self):
        return Calculator()

    def test_add(self, calculator):
        assert calculator.add(2, 3) == 5

    def test_divide_by_zero(self, calculator):
        with pytest.raises(ZeroDivisionError):
            calculator.divide(10, 0)
```

## pytest 配置

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --disable-warnings
    --cov=mypackage
    --cov-report=term-missing
    --cov-report=html
markers =
    slow: 将测试标记为慢速
    integration: 将测试标记为集成测试
    unit: 将测试标记为单元测试
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--cov=mypackage",
    "--cov-report=term-missing",
    "--cov-report=html",
]
markers = [
    "slow: 将测试标记为慢速",
    "integration: 将测试标记为集成测试",
    "unit: 将测试标记为单元测试",
]
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定文件
pytest tests/test_utils.py

# 运行特定测试
pytest tests/test_utils.py::test_function

# 运行并输出详细信息
pytest -v

# 运行并带有覆盖率报告
pytest --cov=mypackage --cov-report=html

# 仅运行非慢速测试
pytest -m "not slow"

# 运行并在第一次失败时停止
pytest -x

# 运行并在 N 次失败后停止
pytest --maxfail=3

# 运行上次失败的测试
pytest --lf

# 运行符合模式的测试
pytest -k "test_user"

# 失败时进入调试器
pytest --pdb
```

## 快速参考

| 模式 | 用途 |
|---------|-------|
| `pytest.raises()` | 测试预期的异常 |
| `@pytest.fixture()` | 创建可重用的测试夹具 |
| `@pytest.mark.parametrize()` | 使用多个输入运行测试 |
| `@pytest.mark.slow` | 标记慢速测试 |
| `pytest -m "not slow"` | 跳过慢速测试 |
| `@patch()` | 模拟函数和类 |
| `tmp_path` 夹具 | 自动生成临时目录 |
| `pytest --cov` | 生成覆盖率报告 |
| `assert` | 简单且可读的断言 |

**记住**：测试代码也是代码。请保持其整洁、可读且易于维护。好的测试能发现 bug；卓越的测试能预防 bug。
