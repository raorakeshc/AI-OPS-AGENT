import time
import logging
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def setup_rag(kb_path: str = "data/kb.txt", retries: int = 3):
    """Attempt to build a retriever from a local KB file. Returns retriever or None."""
    for i in range(retries):
        try:
            loader = TextLoader(kb_path)
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
            splits = text_splitter.split_documents(docs)

            class _CustomGoogleEmbeddings(GoogleGenerativeAIEmbeddings):
                def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return [self.embed_query(text) for text in texts]

            embeddings = _CustomGoogleEmbeddings(model="models/gemini-embedding-2")
            vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
            retriever = vectorstore.as_retriever()
            logging.info("RAG Retriever setup successfully.")
            return retriever
        except Exception as e:
            logging.warning(f"Warning: Failed to setup RAG Tool (Attempt {i+1}/{retries}). Error: {e}")
            if i < retries - 1:
                time.sleep(2)
    logging.error("RAG Retriever unavailable after retries.")
    return None
