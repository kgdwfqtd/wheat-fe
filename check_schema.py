import sys
sys.path.insert(0, '.')
import psycopg2
from config import DB_CONFIG

conn_config = dict(DB_CONFIG)
conn_config['client_encoding'] = 'UTF8'
conn = psycopg2.connect(**conn_config)
cur = conn.cursor()

# 检查所有表的列默认值
tables = ['plots', 'soil_data', 'phenology', 'emergence', 'agronomic_traits', 
          'physiological', 'yield_data', 'quality_data', 'operation_log']

for table in tables:
    cur.execute("""
        SELECT column_name, column_default, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = %s AND column_default IS NULL AND is_nullable = 'NO'
    """, (table,))
    issues = cur.fetchall()
    if issues:
        print(f"\n{table}: 非空但无默认值的列:")
        for col, default, nullable in issues:
            print(f"  - {col}: default={default}, nullable={nullable}")

conn.close()
print("\n检查完成")
