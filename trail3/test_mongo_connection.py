import os
import sys
try:
    from pymongo import MongoClient
    print("pymongo imported successfully.")
except ImportError:
    print("pymongo not found.")
    sys.exit(1)

uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
print(f"Connecting to: {uri}")

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    client.admin.command('ping')
    print("MongoDB connection successful!")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
