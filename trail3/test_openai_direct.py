#!/usr/bin/env python
"""Test OpenAI API directly."""

import os
from dotenv import load_dotenv
load_dotenv()

from llm_engine import openai_client

print("\n=== OpenAI Direct Test ===\n")

if openai_client is None:
    print("✗ OpenAI not configured")
else:
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Say 'OpenAI is working!' in one sentence."}],
            max_tokens=50
        )
        print("✓ OpenAI API SUCCESS!")
        print(f"\nResponse: {response.choices[0].message.content}\n")
    except Exception as e:
        print(f"✗ OpenAI Error: {e}\n")
        print("This means either:")
        print("  1. The API key in .env is invalid/placeholder")
        print("  2. OpenAI account has no credits")
        print("  3. Network issue")
