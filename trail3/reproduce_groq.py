import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1") # Corrected default for testing
# The current code uses https://api.groq.ai/v1 which suspect is wrong.
# Let's test with the one in the code first to prove it fails, or see if it works.
# Actually, let's use the one FROM the code to reproduce the issue exactly.

code_base_url = "https://api.groq.ai/v1"

print(f"Testing with API Key: {api_key[:5]}...")
print(f"Testing with Base URL: {code_base_url}")

client = OpenAI(api_key=api_key, api_base=code_base_url)

try:
    resp = client.chat.completions.create(
        model="gpt-4o-mini", # This is what the code uses
        messages=[{"role": "user", "content": "Hello, are you working?"}],
    )
    print("Success!")
    print(resp.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")

print("-" * 20)
print("Testing with CORRECT Base URL and Model...")
correct_base_url = "https://api.groq.com/openai/v1"
correct_model = "llama3-70b-8192"

client_correct = OpenAI(api_key=api_key, api_base=correct_base_url)
try:
    resp = client_correct.chat.completions.create(
        model=correct_model,
        messages=[{"role": "user", "content": "Hello, are you working?"}],
    )
    print("Success with Correct Settings!")
    print(resp.choices[0].message.content)
except Exception as e:
    print(f"Error with Correct Settings: {e}")
