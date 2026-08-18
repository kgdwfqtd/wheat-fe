# -*- coding: utf-8 -*-
"""兼容层：保留旧导入路径，但统一使用新配置中心。"""

from wheat_app.config import *  # noqa: F401,F403

# 兼容旧代码：import config 时仍可工作
