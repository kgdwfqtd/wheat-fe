import sys
sys.path.insert(0, '.')

from database import (
    get_all_plots,
    get_all_bases,
    get_completion_stats,
    get_treatment_table_matrix,
    get_operations,
)

# Test all functions for NaN values
print("=== Testing get_all_plots ===")
try:
    plots = get_all_plots()
    records = plots.to_dict(orient='records')
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and v != v:  # NaN check
                print(f"  NaN found in plots.{k}")
    print(f"  OK: {len(records)} records")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== Testing get_completion_stats ===")
try:
    stats = get_completion_stats()
    # Check recursively for NaN
    def check_nan(obj, path=""):
        if isinstance(obj, float) and obj != obj:
            print(f"  NaN found at: {path}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                check_nan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_nan(v, f"{path}[{i}]")
    check_nan(stats)
    print("  OK")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== Testing get_treatment_table_matrix ===")
try:
    matrix = get_treatment_table_matrix()
    check_nan(matrix, "matrix")
    print("  OK")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== Testing get_operations ===")
try:
    ops = get_operations(limit=5)
    records = ops.to_dict(orient='records')
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and v != v:
                print(f"  NaN found in operations.{k}")
    print(f"  OK: {len(records)} records")
except Exception as e:
    print(f"  ERROR: {e}")

print("\nDone!")
