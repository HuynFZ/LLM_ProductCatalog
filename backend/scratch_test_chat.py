import requests
import json

resp = requests.post(
    "http://127.0.0.1:8080/api/chat",
    json={"query": "tìm trang phục ấm áp giữ nhiệt mùa đông màu đen"},
    timeout=60
)
print("STATUS CODE:", resp.status_code)
data = resp.json()
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("AI RESPONSE:\n", data.get("ai_response"))
products = data.get("products_data", [])
print(f"\nTOTAL PRODUCTS RETURNED: {len(products)}")
for p in products:
    print(f"  * [{p.get('id')}] {p.get('name')} | Điểm: {p.get('match_score')}% | Lý do: {p.get('match_reason')} | Giá: ${p.get('original_price')}")
