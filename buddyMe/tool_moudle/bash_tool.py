"""
================================================================================
BashTool - Bash 命令执行工具
================================================================================

根据 anthropic-document.md 规范实现的工具模块。

继承 BaseTool，提供基础的 shell 命令执行能力、定时任务、循环任务等功能。

工具列表:
    - BashTool: 执行 Bash/Shell 命令
    - ReadFileTool: 读取文件内容
    - WriteFileTool: 写入文件内容
    - EditFileTool: 编辑文件内容
    - GrepTool: 文件内容搜索（正则匹配）
    - GlobTool: 文件名模式匹配查找


================================================================================
"""

import os
import re
import asyncio
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional
from buddyMe.anthropic_standard.basic_anthropic_tool import BaseTool


# ==============================================================================
# 工具定义
# ==============================================================================




class BashTool(BaseTool):
    """Bash 命令执行工具"""

    def __init__(self):
        super().__init__(
            name="bash",
            description="""执行 Bash/Shell 命令，操作系统原生命令行工具。

【适用场景】
- 文件操作：创建目录、复制、移动、删除文件
- 运行脚本：执行 .sh/.bat/.py 等脚本
- Git 操作：commit、push、pull、log 等
- 程序运行：启动服务、运行编译后的程序
- 系统信息：查看进程、网络状态、磁盘空间

【输入参数】
- command (必需): 要执行的命令字符串
- timeout (可选): 超时时间秒数，默认 30 秒
- cwd (可选): 工作目录，默认当前目录

【输出】
- 返回命令的标准输出和标准错误

【安全限制】
- 危险命令被拦截（如 rm -rf /、mkfs 等）
- 超时后命令会被强制终止""",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 bash 命令（字符串）"
                    },
                    "timeout": {
                        "type": "number",
                        "description": "命令超时时间（秒），默认 30 秒",
                        "default": 30
                    },
                    "cwd": {
                        "type": "string",
                        "description": "命令执行的工作目录，默认为当前目录"
                    }
                },
                "required": ["command"]
            }
        )

    async def execute(self, command: str, timeout: float = 30, cwd: Optional[str] = None) -> str:
        """执行 bash 命令（异步，不阻塞事件循环）"""
        if not command or not command.strip():
            return "错误：命令不能为空"

        # 安全检查
        dangerous_patterns = ["rm -rf /", "mkfs", ":(){ :|:& };:", "dd if=/dev/zero"]
        for pattern in dangerous_patterns:
            if pattern in command:
                return f"错误：检测到危险命令模式 '{pattern}'，拒绝执行"

        # Windows: PowerShell 命令自动追加非交互标志，防止挂起
        if os.name == "nt" and re.match(r"^\s*powershell\b", command, re.IGNORECASE):
            if "-NonInteractive" not in command:
                command = command.replace("powershell", "powershell -NoProfile -NonInteractive", 1)

        try:
            work_dir = cwd if cwd else os.getcwd()

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            stdout_text = self._decode_output(stdout) if stdout else ""
            stderr_text = self._decode_output(stderr) if stderr else ""

            output_parts = []
            if stdout_text:
                output_parts.append(stdout_text)
            if stderr_text:
                output_parts.append(f"[stderr]\n{stderr_text}")
            if proc.returncode != 0 and not stdout_text and not stderr_text:
                output_parts.append(f"[exit code: {proc.returncode}]")

            if output_parts:
                return "\n".join(output_parts)
            else:
                return "[命令执行完成，无输出]"

        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"错误：命令执行超时（{timeout}秒）"
        except FileNotFoundError:
            return "错误：命令未找到。请确认命令存在且在 PATH 中。"
        except PermissionError:
            return "错误：权限不足，无法执行该命令"
        except Exception as e:
            return f"错误：命令执行失败 - {str(e)}"

    @staticmethod
    def _decode_output(raw: bytes) -> str:
        """优先 UTF-8 解码，失败回退 GBK，再失败用 replace 模式"""
        for encoding in ("utf-8", "gbk"):
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode("utf-8", errors="replace")

class ReadFileTool(BaseTool):
    """文件读取工具"""

    def __init__(self):
        super().__init__(
            name="read_file",
            description="""读取文件内容，适合分析已有数据、代码、配置等。

【适用场景】
- 分析代码文件了解项目结构
- 读取配置文件（.json/.yaml/.env 等）
- 查看日志文件内容
- 检查文档内容
- 验证之前 write_file 操作的结果

【输入参数】
- path (必需): 文件路径（绝对路径或相对路径）
- limit (可选): 最多读取的行数，默认全部读取
- offset (可选): 从第几行开始读取（从1开始），用于大文件分段读取

【输出】
- 返回文件路径、行数、大小和内容
- 大文件自动保留首尾关键部分，中间省略（可用 grep 搜索具体内容）""",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径（绝对路径或相对路径）"
                    },
                    "limit": {
                        "type": "number",
                        "description": "最多读取的行数（可选，默认全部读取）"
                    },
                    "offset": {
                        "type": "number",
                        "description": "从第几行开始读取（从1开始），用于大文件分段读取"
                    }
                },
                "required": ["path"]
            }
        )

    async def execute(self, path: str, limit: Optional[int] = None, offset: Optional[int] = None) -> str:
        try:
            abs_path = Path(path).resolve()
            if not abs_path.exists():
                return f"错误：文件 {path} 不存在"

            file_size = abs_path.stat().st_size

            all_lines = abs_path.read_text(encoding="utf-8").splitlines(keepends=True)

            total_lines = len(all_lines)

            # offset/limit：从 all_lines 中切片
            start = (offset - 1) if offset and offset > 1 else 0
            if limit:
                selected = all_lines[start:start + limit]
            else:
                selected = all_lines[start:]

            content = ''.join(selected)
            read_lines = len(selected)

            # 大文件智能保留首尾（一次返回完整视图，不需要 LLM 分段读取）
            if len(content) > 50000:
                head = content[:35000]
                tail = content[-15000:]
                skipped = len(content) - 35000 - 15000
                content = (
                    head
                    + f"\n\n...[中间省略 {skipped} 字符，"
                    + f"共 {read_lines} 行，如需查看中间部分请用 grep 搜索关键词]...\n\n"
                    + tail
                )

            header = f"文件: {abs_path} (共 {total_lines} 行, {file_size} 字节)"
            if offset:
                header += f" | 从第 {offset} 行开始"
            if limit:
                header += f" | 读取 {read_lines} 行"

            return f"{header}\n内容:\n{content}"
        except PermissionError:
            return f"错误：没有读取文件 {path} 的权限"
        except Exception as e:
            return f"读取文件失败：{str(e)}"


class WriteFileTool(BaseTool):
    """文件写入工具"""

    def __init__(self):
        super().__init__(
            name="write_file",
            description="""写入内容到文件，文件不存在则创建，存在则覆盖。

【适用场景】
- 生成报告文件（.md/.txt/.json 等）
- 创建或修改配置文件
- 保存搜索结果、分析数据
- 写入代码文件
- 创建日志输出文件

【输入参数】
- path (必需): 文件路径
- content (必需): 要写入的文本内容

【输出】
- 返回写入成功信息和字符数

【注意】
- 会覆盖已存在的同名文件
- 自动创建父目录（如果不存在）""",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径（绝对路径或相对路径）"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文本内容"
                    }
                },
                "required": ["path", "content"]
            }
        )

    async def execute(self, path: str, content: str) -> str:
        try:
            abs_path = Path(path).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content, encoding="utf-8")
            return f"成功写入文件 {abs_path}，共 {len(content)} 字符"
        except PermissionError:
            return f"错误：没有写入文件 {path} 的权限"
        except Exception as e:
            return f"写入文件失败：{str(e)}"


class EditFileTool(BaseTool):
    """文件编辑工具"""

    def __init__(self):
        super().__init__(
            name="edit_file",
            description="""精确编辑文件，替换文件中的特定文本。

【适用场景】
- 修改配置文件中的某个值
- 修改代码文件中的某行或某段
- 替换文档中的特定文本
- 修复文件中的错误

【输入参数】
- path (必需): 文件路径
- old_string (必需): 要被替换的原始文本（必须完全匹配）
- new_string (必需): 替换后的新文本
- replace_all (可选): 是否替换所有匹配项，默认 False

【输出】
- 返回替换成功信息和替换次数

【限制】
- old_string 必须在文件中完全匹配（包括空格、换行）""",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要编辑的文件路径（绝对路径或相对路径）"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "要被替换的原始文本（必须完全匹配）"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "替换后的新文本"
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "是否替换所有匹配项（默认false，只替换第一个）",
                        "default": False
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        )

    async def execute(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        try:
            abs_path = Path(path).resolve()

            if not abs_path.exists():
                return f"错误：文件 {path} 不存在"

            content = abs_path.read_text(encoding="utf-8")

            if old_string not in content:
                return "错误：未找到要替换的文本。请确保 old_string 完全匹配（包括空格和换行）"

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            abs_path.write_text(new_content, encoding="utf-8")

            return f"成功编辑文件 {abs_path}，替换了 {count} 处"
        except PermissionError:
            return f"错误：没有编辑文件 {path} 的权限"
        except Exception as e:
            return f"编辑文件失败：{str(e)}"


class GrepTool(BaseTool):
    """文件内容搜索工具（正则匹配）"""

    def __init__(self):
        super().__init__(
            name="grep",
            description="""在文件内容中搜索匹配的文本行，支持正则表达式。

【适用场景】
- 在代码中查找函数定义、变量引用
- 搜索配置文件中的特定配置项
- 查找错误信息、日志关键字
- 定位代码中使用了某个 API 的位置

【输入参数】
- pattern (必需): 搜索模式，支持正则表达式（如 "def \\w+"、"import.*os"）
- path (可选): 搜索目录或文件路径，默认当前工作目录
- include (可选): 文件名过滤，如 "*.py"、"*.md"，默认搜索所有文件
- max_results (可选): 最多返回的匹配数，默认 100

【输出】
- 匹配行及其文件路径和行号""",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "搜索模式（支持正则表达式，如 'def \\w+'、'import.*os'）"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索的目录或文件路径，默认为当前工作目录"
                    },
                    "include": {
                        "type": "string",
                        "description": "文件名过滤模式（如 '*.py'、'*.{ts,tsx}'），默认搜索所有文件"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "最多返回的匹配结果数，默认 100",
                        "default": 100
                    }
                },
                "required": ["pattern"]
            }
        )

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        include: Optional[str] = None,
        max_results: int = 100
    ) -> str:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"错误：无效的正则表达式 - {e}"

        search_path = Path(path).resolve() if path else Path.cwd()

        if not search_path.exists():
            return f"错误：路径 {search_path} 不存在"

        # 解析 include 模式（支持 *.{py,js} 格式）
        include_patterns = self._parse_include(include) if include else None

        results = []
        files_searched = 0

        if search_path.is_file():
            # 搜索单个文件
            files_searched = 1
            self._search_file(str(search_path), compiled, results, max_results)
        else:
            # 搜索目录
            for root, dirs, files in os.walk(str(search_path)):
                # 跳过隐藏目录和常见忽略目录
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in (
                    'node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'build'
                )]
                for filename in files:
                    if include_patterns and not any(fnmatch.fnmatch(filename, p) for p in include_patterns):
                        continue
                    filepath = os.path.join(root, filename)
                    self._search_file(filepath, compiled, results, max_results)
                    files_searched += 1
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break

        if not results:
            return f"未找到匹配项（搜索了 {files_searched} 个文件）"

        output_lines = [f"搜索了 {files_searched} 个文件，找到 {len(results)} 个匹配项：\n"]
        for filepath, lineno, line in results[:max_results]:
            rel_path = os.path.relpath(filepath, str(search_path)) if search_path.is_dir() else filepath
            output_lines.append(f"{rel_path}:{lineno}: {line.rstrip()}")

        if len(results) > max_results:
            output_lines.append(f"\n... 还有 {len(results) - max_results} 个匹配项未显示")

        return "\n".join(output_lines)

    @staticmethod
    def _parse_include(include: str) -> List[str]:
        """解析 include 模式，支持 *.{py,js} 格式"""
        if '{' in include and '}' in include:
            prefix = include[:include.index('{')]
            exts = include[include.index('{') + 1:include.index('}')].split(',')
            return [f"{prefix}{ext.strip()}" for ext in exts]
        return [include]

    @staticmethod
    def _search_file(filepath: str, pattern: re.Pattern, results: list, max_results: int):
        """搜索单个文件，将匹配行添加到 results"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        results.append((filepath, lineno, line))
                        if len(results) >= max_results:
                            return
        except (PermissionError, OSError):
            pass


class GlobTool(BaseTool):
    """文件名模式匹配查找工具"""

    def __init__(self):
        super().__init__(
            name="glob",
            description="""按文件名模式查找文件，支持通配符和递归搜索。

【适用场景】
- 查找特定类型的文件（如所有 .py、.md 文件）
- 定位某个文件在项目中的位置
- 查看目录结构中包含哪些文件

【输入参数】
- pattern (必需): 文件名匹配模式，支持通配符
  - * 匹配任意字符（不含路径分隔符）
  - ** 匹配任意层级目录
  - 示例：'**/*.py'、'src/**/*.ts'、'*config*'
- path (可选): 搜索根目录，默认当前工作目录
- max_results (可选): 最多返回的文件数，默认 200

【输出】
- 匹配的文件路径列表""",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "文件名匹配模式（如 '**/*.py'、'src/**/*.ts'、'*config*'）"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索根目录，默认为当前工作目录"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "最多返回的文件数，默认 200",
                        "default": 200
                    }
                },
                "required": ["pattern"]
            }
        )

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        max_results: int = 200
    ) -> str:
        import glob as glob_module

        search_path = Path(path).resolve() if path else Path.cwd()

        if not search_path.exists():
            return f"错误：路径 {search_path} 不存在"

        full_pattern = str(search_path / pattern)
        matches = glob_module.glob(full_pattern, recursive=True)

        # 过滤掉隐藏文件和常见忽略目录中的文件
        ignore_dirs = {'node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'build'}
        filtered = [
            m for m in matches
            if not any(part.startswith('.') or part in ignore_dirs for part in os.path.relpath(m, str(search_path)).split(os.sep))
            and os.path.isfile(m)
        ]

        if not filtered:
            return f"未找到匹配 '{pattern}' 的文件（搜索目录: {search_path}）"

        # 按修改时间排序（最近的在前）
        filtered.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        filtered = filtered[:max_results]

        # 转为相对路径
        rel_paths = [os.path.relpath(f, str(search_path)) for f in filtered]

        output_lines = [f"找到 {len(rel_paths)} 个匹配 '{pattern}' 的文件：\n"]
        output_lines.extend(rel_paths)

        total = len(glob_module.glob(full_pattern, recursive=True))
        if total > max_results:
            output_lines.append(f"\n... 共 {total} 个文件，仅显示前 {max_results} 个")

        return "\n".join(output_lines)