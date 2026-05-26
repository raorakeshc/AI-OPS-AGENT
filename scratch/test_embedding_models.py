import os
import sys
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import GoogleGenerativeAIEmbeddings

models = ["models/gemini-embedding-2", "models/embedding-001", "models/text-embedding-004"]
texts = ["hello world", "foo bar", "test query"]

for m in models:
    try:
        e = GoogleGenerativeAIEmbeddings(model=m)
        res = e.embed_documents(texts)
        print(f"Model: {m} -> Input: {len(texts)} -> Output: {len(res)}")
    except Exception as ex:
        print(f"Model: {m} -> Error: {ex}")
