import os
from dotenv import load_dotenv, find_dotenv

# Force load env before importing engine to ensure variables are present
load_dotenv(find_dotenv(), override=True)

import llm_engine

print("Testing simple LLM call...")
try:
    response = llm_engine.call_llm("Say 'hello world'", mode="fast")
    print(f"Fast Mode Response: {response}")
except Exception as e:
    print(f"Fast Mode Failed: {e}")

print("\nTesting validation...")
try:
    val_response = llm_engine.llm_validate("Some random text")
    print(f"Validation Response: {val_response}")
except Exception as e:
    print(f"Validation Failed: {e}")
