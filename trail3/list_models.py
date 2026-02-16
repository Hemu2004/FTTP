from google import genai
import os

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not found.")

client = genai.Client(api_key=api_key)

models = client.models.list()
for model in models:
    print(model.name)
