"""统一的项目配置与数据访问入口。

此包用于提供更规范的代码组织方式，同时保留旧版根目录导入兼容。

注意：避免在 __init__ 中自动导入 repository/service，防止循环依赖。
"""

from .config import *

__all__ = [
    "BASE_DIR",
    "DB_CONFIG",
    "DB_URL",
    "DB_BACKUP_MAX",
    "PLOT_AREA_M2",
    "PLOT_RATIO",
    "NF_SPLIT",
    "NF_SPRAY_WATER_L_PER_MU",
    "TKW_DIFF_WARN_PCT",
    "EMERGENCE_RATE_WARN",
    "PAGE_TITLE",
    "PAGE_ICON",
    "PROJECT_ROOT",
]
