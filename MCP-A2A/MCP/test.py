from openai import OpenAI

client = OpenAI(api_key = "sk-hR2UrPTL2iMqdYUtux6jK70PHB9TTH8QSaMC59qESK4QJvkb", base_url = "https://blueshirtmap.com/v1")

response = client.chat.completions.create(model='Qwen/Qwen2-72B-Instruct', messages=[{"role": "user", "content": "地球一天几个小时？"}])
evaluation_response = response.choices[0].message.content
print(evaluation_response)