from openai import OpenAI
client = OpenAI(api_key = "sk-MfsGu5ILuHxYMuoSGYAbX0lwMMO2rnfjIqMZGxI0RgLaf89Y",base_url = "https://www.blueshirtmap.com/v1")

response = client.chat.completions.create(model='gpt-4o-mini',messages=[{"role": "user", "content": "你是谁？"}])
evaluation_response = response.choices[0].message.content

print(evaluation_response)