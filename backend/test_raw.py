import sys
import json
import requests
from llm_agent import cot_unified_search_intent

sys.stdout.reconfigure(encoding='utf-8')
q = "Tìm một bộ jumpsuit dạo phố màu đen size M giá dưới 300"
res = cot_unified_search_intent(q)
print("res:", res)



