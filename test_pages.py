import sys
sys.path.insert(0, '.')

# 测试所有页面文件的导入 - 静默模式
import warnings
warnings.filterwarnings('ignore')

# 重定向 stderr
import os
original_stderr = sys.stderr
sys.stderr = open(os.devnull, 'w')

pages = [
    'pages.01_plots',
    'pages.02_soil',
    'pages.03_phenology', 
    'pages.04_agronomic',
    'pages.05_physiological',
    'pages.06_yield',
    'pages.07_quality',
    'pages.08_operations',
    'pages.09_export',
    'pages.10_qrcode',
    'pages.12_base_management',
]

import importlib
results = []
for page in pages:
    try:
        mod = importlib.import_module(page)
        results.append(f"OK: {page}")
    except Exception as e:
        results.append(f"ERROR: {page}: {type(e).__name__}: {str(e)[:100]}")

# 恢复 stderr
sys.stderr.close()
sys.stderr = original_stderr

# 输出结果
for r in results:
    print(r)

# 测试核心模块
print("\n--- Testing core modules ---")
try:
    from wheat_app.services.experiment_service import get_dashboard_snapshot
    result = get_dashboard_snapshot()
    print("OK: experiment_service.get_dashboard_snapshot()")
except Exception as e:
    print(f"ERROR: experiment_service: {type(e).__name__}: {str(e)[:100]}")

try:
    from wheat_app.repositories.experiment_repository import init_db, init_plots
    print("OK: experiment_repository imports")
except Exception as e:
    print(f"ERROR: experiment_repository: {type(e).__name__}: {str(e)[:100]}")

print("\nDone!")
