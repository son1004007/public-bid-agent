import django
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bid_server.settings.local")
sys.path.insert(0, r"C:\Users\User\source\public-bid-agent-bid03\server")

django.setup()

from django.test import Client

client = Client()

# 1. Load workspace
res_ws = client.get('/workspace')
assert res_ws.status_code == 200, f'Workspace failed: {res_ws.status_code}'
print("1. [OK] GET /workspace rendered 200 OK")

# 2. Get CSRF
res_csrf = client.get('/api/v1/auth/csrf')
assert res_csrf.status_code == 200
csrf_token = res_csrf.json()['data']['csrf_token']
print(f"2. [OK] GET /api/v1/auth/csrf -> CSRF Token: {csrf_token[:12]}...")

# 3. Login as director
res_login = client.post(
    '/api/v1/auth/login',
    {'username': 'director', 'password': 'Password1234!@#$'},
    content_type='application/json',
    HTTP_X_CSRFTOKEN=csrf_token,
    HTTP_ORIGIN='http://127.0.0.1:8000'
)
assert res_login.status_code == 200, f'Login failed: {res_login.status_code} {res_login.content}'
print("3. [OK] POST /api/v1/auth/login -> Logged in as director (김총괄 이사)")

# 4. Query Dashboard
res_dash = client.get('/api/v1/dashboard')
assert res_dash.status_code == 200
dash_data = res_dash.json()['data']
print("4. [OK] GET /api/v1/dashboard -> Live DB stats:")
for k, v in dash_data['counts'].items():
    print(f"    - {k}: {v:,}")

# 5. Query Notices (AI)
res_ai = client.get('/api/v1/notices?field=AI&limit=5')
assert res_ai.status_code == 200
ai_items = res_ai.json()['data']
print(f"\n5. [OK] GET /api/v1/notices?field=AI -> Retrieved {len(ai_items)} AI notices:")
for item in ai_items[:3]:
    bg_str = f"{item['budget_amount']:,}원" if item.get('budget_amount') else "미기재"
    print(f"    - [{item['deadline_status']}] {item['title'][:40]} ({item['buyer']}) | {bg_str}")

# 6. Detail of first AI notice
first_id = ai_items[0]['id']
res_detail = client.get(f'/api/v1/notices/{first_id}')
assert res_detail.status_code == 200
detail_data = res_detail.json()['data']
print(f"\n6. [OK] GET /api/v1/notices/{first_id} -> Notice Details:")
print(f"    - Title: {detail_data['title']}")
print(f"    - Buyer: {detail_data['buyer']}")
print(f"    - Budget: {detail_data['budget_amount']:,}원")
print(f"    - Attached Documents: {len(detail_data.get('documents', []))} files")

print("\n=======================================================")
print("  🎉 SM06 E2E WORKSPACE & API VERTICAL INTEGRATION 100% OK!  ")
print("=======================================================")
