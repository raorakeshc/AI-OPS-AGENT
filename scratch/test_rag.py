import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Set PYTHONPATH to root
sys.path.insert(0, os.getcwd())

from src.rag import setup_rag

print("Initializing RAG...")
retriever = setup_rag()
if retriever:
    print("RAG Retriever initialized successfully!")
    docs = retriever.invoke("what is your refund policy")
    print(f"Retrieved {len(docs)} documents:")
    for d in docs:
        print("-", d.page_content[:150], "...")
else:
    print("Failed to initialize RAG Retriever!")
