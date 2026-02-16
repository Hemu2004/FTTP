#!/usr/bin/env python
"""Quick test of OpenAI API."""

import os
from dotenv import load_dotenv
load_dotenv()

print("\n=== Checking API Configuration ===\n")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'NOT SET')[:20]}...")
print(f"XAI_API_KEY: {os.getenv('XAI_API_KEY', 'NOT SET')[:20]}...")
print()

try:
    from llm_engine import call_llm
    print("Testing call_llm()...\n")
    response = call_llm("Say 'API is working!' in one sentence.")
    print("✓ Success!")
    print(f"Response: {response}\n")
except Exception as e:
    print(f"✗ Error: {e}\n")
