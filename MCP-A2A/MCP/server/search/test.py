import requests
import json

url = "https://api.bochaai.com/v1/web-search"
payload = json.dumps({
  "query": "阿里巴巴2024年的ESG报告",
  "summary": True,
  "freshness": "noLimit",
  "count": 10
})
headers = {
  'Authorization': 'Bearer sk-0b460bd4bc80408d8cba2238c90a1649',  # 👈 您的密钥已放在这里
  'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)
print(response.text)