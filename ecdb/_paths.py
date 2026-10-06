"""路径解析：所有路径基于本文件位置推导，与运行时 CWD 无关。

项目文件夹整体移动后无需修改任何代码。可用环境变量覆盖：
    ECDB_ROOT  项目根目录（默认：本包上一级目录）
    ECDB_DATA  原始 CSV 目录（默认：<root>/data_from_EI）
    ECDB_DB    数据库文件路径（默认：<root>/db/ec_papers.db）
"""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def project_root():
    return Path(os.environ.get("ECDB_ROOT", PACKAGE_DIR.parent)).resolve()


def data_dir():
    return Path(os.environ.get("ECDB_DATA", project_root() / "data_from_EI")).resolve()


def db_path():
    return Path(os.environ.get("ECDB_DB", project_root() / "db" / "ec_papers.db")).resolve()


def iter_source_files(directory=None):
    """按文件名排序返回原始 CSV 列表（排序保证导入结果确定性）。"""
    d = Path(directory) if directory else data_dir()
    return sorted(d.glob("*.csv"))
