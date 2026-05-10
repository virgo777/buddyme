"""跨平台原子文件写入"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Union


def atomic_write(path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
    """原子写入文件：先写同目录临时文件，fsync 后 os.replace 替换。

    处理 Windows/Linux 跨文件系统回退，保证写入不丢数据。
    """
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(
        dir=str(target.parent), prefix="." + target.name + ".", suffix=".tmp"
    )
    try:
        with open(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, str(target))
        except OSError:
            shutil.copy2(tmp, str(target))
            os.remove(tmp)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
