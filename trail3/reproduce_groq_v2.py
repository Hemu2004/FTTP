import os
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

# Force reload of .env to ensure we get the file's content
load_dotenv(find_dotenv(), override=True)

api_key = os.getenv("GROQ_API_KEY")
# Default to the correct Groq URL
base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1") 

print(f"Testing with API Key: {api_key[:10]}..." if api_key else "API Key NOT FOUND")
print(f"Testing with Base URL: {base_url}")

if not api_key:
    print("CRITICAL: GROQ_API_KEY is missing!")
    exit(1)

# Use base_url instead of api_base
client = OpenAI(api_key=api_key, base_url=base_url)

target_model = "llama3-70b-8192" # A standard Groq model

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
