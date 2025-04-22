import os
from openai import OpenAI
 # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
client = OpenAI(api_key='sk-761e2c94037c45eba58f3c0112d2f4af', base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
# 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
completion = client.chat.completions.create(model="qwen2.5-7b-instruct-1m",messages=[{'role': 'system', 'content': 'You are a helpful assistant.'},{'role': 'user', 'content': '地球一天几个小时？'}])  
print(completion.model_dump_json())