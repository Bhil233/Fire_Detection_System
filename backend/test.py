import os


api = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")

print(api)
