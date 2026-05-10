---
name: content-hash-cache-pattern
description: 使用 SHA-256 内容哈希缓存高昂的文件处理结果 —— 与路径无关、自动失效且服务层分离。
origin: ECC
---

# 内容哈希文件缓存模式 (Content-Hash File Cache Pattern)

使用 SHA-256 内容哈希（而非文件路径）作为缓存键，缓存高昂的文件处理结果（如 PDF 解析、文本提取、图像分析）。与基于路径的缓存不同，这种方法在文件移动/重命名后依然有效，并在内容变化时自动失效。

## 何时激活

- 构建文件处理流水线（Pipeline），如 PDF、图像或文本提取
- 处理成本高昂且需要重复处理相同文件
- 需要提供 `--cache/--no-cache` 命令行选项
- 希望在不修改现有纯函数（Pure Functions）的情况下为其添加缓存功能

## 核心模式

### 1. 基于内容哈希的缓存键

使用文件内容（而非路径）作为缓存键：

```python
import hashlib
from pathlib import Path

_HASH_CHUNK_SIZE = 65536  # 大文件采用 64KB 分块读取

def compute_file_hash(path: Path) -> str:
    """计算文件内容的 SHA-256 哈希值（针对大文件进行分块）。"""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()
```

**为什么使用内容哈希？** 文件重命名/移动 = 缓存命中。内容更改 = 自动失效。无需索引文件。

### 2. 用于缓存条目的冻结数据类 (Frozen Dataclass)

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class CacheEntry:
    file_hash: str
    source_path: str
    document: ExtractedDocument  # 缓存的结果内容
```

### 3. 基于文件的缓存存储

每个缓存条目存储为 `{hash}.json` —— 通过哈希实现 O(1) 查询，无需索引文件。

```python
import json
from typing import Any

def write_cache(cache_dir: Path, entry: CacheEntry) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{entry.file_hash}.json"
    data = serialize_entry(entry)
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

def read_cache(cache_dir: Path, file_hash: str) -> CacheEntry | None:
    cache_file = cache_dir / f"{file_hash}.json"
    if not cache_file.is_file():
        return None
    try:
        raw = cache_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        return deserialize_entry(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        return None  # 将损坏的缓存视为未命中
```

### 4. 服务层封装 (满足单一职责原则 SRP)

保持处理函数为纯函数。将缓存逻辑作为独立的服务层添加。

```python
def extract_with_cache(
    file_path: Path,
    *,
    cache_enabled: bool = True,
    cache_dir: Path = Path(".cache"),
) -> ExtractedDocument:
    """服务层逻辑：检查缓存 -> 提取内容 -> 写入缓存。"""
    if not cache_enabled:
        return extract_text(file_path)  # 纯函数，不感知缓存逻辑

    file_hash = compute_file_hash(file_path)

    # 检查缓存
    cached = read_cache(cache_dir, file_hash)
    if cached is not None:
        logger.info("Cache hit: %s (hash=%s)", file_path.name, file_hash[:12])
        return cached.document

    # 缓存未命中 -> 提取 -> 存储
    logger.info("Cache miss: %s (hash=%s)", file_path.name, file_hash[:12])
    doc = extract_text(file_path)
    entry = CacheEntry(file_hash=file_hash, source_path=str(file_path), document=doc)
    write_cache(cache_dir, entry)
    return doc
```

## 关键设计决策

| 决策 | 理由 |
|----------|-----------|
| SHA-256 内容哈希 | 与路径无关，内容更改时自动失效 |
| `{hash}.json` 文件命名 | O(1) 查询速度，无需维护索引文件 |
| 服务层封装 (Wrapper) | 满足单一职责原则（SRP）：提取逻辑保持纯净，缓存作为独立关注点 |
| 手动 JSON 序列化 | 对冻结数据类的序列化拥有完全控制权 |
| 损坏返回 `None` | 优雅降级，在下次运行时重新处理 |
| `cache_dir.mkdir(parents=True)` | 在首次写入时延迟创建目录 |

## 最佳实践

- **哈希内容而非路径** —— 路径会变，内容身份（Identity）不变。
- **对大文件进行分块哈希** —— 避免将整个文件加载进内存。
- **保持处理函数纯净** —— 它们不应知道任何关于缓存的信息。
- **记录缓存命中/未命中日志** —— 使用截断后的哈希值以便调试。
- **优雅处理缓存损坏** —— 将无效的缓存条目视为未命中，绝不要因此崩溃。

## 应避免的反模式 (Anti-Patterns)

```python
# 错误做法：基于路径的缓存（文件移动/重命名后失效）
cache = {"/path/to/file.pdf": result}

# 错误做法：在处理函数内部添加缓存逻辑（违反 SRP）
def extract_text(path, *, cache_enabled=False, cache_dir=None):
    if cache_enabled:  # 该函数现在有了双重职责
        ...

# 错误做法：对嵌套的冻结数据类直接使用 dataclasses.asdict()
# (在处理复杂的嵌套类型时可能会出现问题)
data = dataclasses.asdict(entry)  # 推荐使用手动序列化
```

## 适用场景

- 文件处理流水线（PDF 解析、OCR、文本提取、图像分析）
- 受益于 `--cache/--no-cache` 选项的命令行工具 (CLI)
- 在不同运行周期中会出现相同文件的批处理任务
- 在不修改现有纯函数的情况下为其添加缓存功能

## 不适用场景

- 必须保持绝对实时的数据（实时数据流）
- 缓存条目体积极其庞大（此时应考虑流式处理）
- 结果取决于文件内容以外的参数（例如不同的提取配置）
