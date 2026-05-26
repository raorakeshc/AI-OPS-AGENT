import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.getcwd())

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.config import get_config

config = get_config()
loader = TextLoader(config.rag.kb_filepath)
docs = loader.load()
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.rag.chunk_size,
    chunk_overlap=config.rag.chunk_overlap,
)
splits = text_splitter.split_documents(docs)
print(f"Total splits: {len(splits)}")
for i, s in enumerate(splits):
    print(f"Split {i}: length={len(s.page_content)}, content={repr(s.page_content)}")

embeddings = GoogleGenerativeAIEmbeddings(model=config.rag.embeddings_model)
texts = [s.page_content for s in splits]
print(f"Embedding {len(texts)} texts...")
res = embeddings.embed_documents(texts)
print(f"Embeddings returned: {len(res)}")
