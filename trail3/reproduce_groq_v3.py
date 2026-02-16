import os
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

# Force reload of .env
load_dotenv(find_dotenv(), override=True)

api_key = os.getenv("GROQ_API_KEY")
base_url = "https://api.groq.com/openai/v1"

print(f"Testing with API Key: {api_key[:10]}...")
print(f"Testing with Base URL: {base_url}")

client = OpenAI(api_key=api_key, base_url=base_url)

# Try the versatile model
target_model = "llama-3.3-70b-versatile" 

print(f"Attempting valid request to model: {target_model}")

try:
    resp = client.chat.completions.create(
        model=target_model,
        messages=[{"role": "user", "content": "Return a single word: 'connected'"}],
    )
    print("Success!")
    print(f"Response: {resp.choices[0].message.content}")
except Exception as e:
    print(f"Error: {e}")
