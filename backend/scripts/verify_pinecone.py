# scripts/verify_pinecone.py
from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
print("Indexes visible to this key:", pc.list_indexes().names())

index = pc.Index("cedric-ai-chunks")
print("Index stats:", index.describe_index_stats())