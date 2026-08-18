import sys
sys.path.insert(0, '.')

# Test backend with TestClient
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

# Test table/soil_data
print("=== Testing /api/v1/table/soil_data ===")
response = client.get('/api/v1/table/soil_data')
data = response.json()
print(f"Status: {response.status_code}")
print(f"Message: {data.get('message')}")
table_data = data.get('data', [])
print(f"Records count: {len(table_data)}")
if table_data:
    # Check for NaN in first record
    first = table_data[0]
    for k, v in first.items():
        if isinstance(v, float) and v != v:  # NaN check
            print(f"  NaN found in {k}")

# Test dashboard
print("\n=== Testing /api/v1/dashboard ===")
response = client.get('/api/v1/dashboard')
data = response.json()
print(f"Status: {response.status_code}")
print(f"Message: {data.get('message')}")

# Check all table endpoints
tables = ['soil_data', 'phenology', 'emergence', 'agronomic_traits', 
          'physiological', 'yield_data', 'quality_data', 'operation_log']

for table in tables:
    try:
        response = client.get(f'/api/v1/table/{table}')
        data = response.json()
        count = len(data.get('data', []))
        print(f"  {table}: {response.status_code} - {data.get('message')} ({count} records)")
    except Exception as e:
        print(f"  {table}: ERROR - {e}")

print("\nDone!")
