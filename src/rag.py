import time
import logging
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from .config import get_config


def setup_rag(config: Any = None, retries: int = 3):
    """Initialize a semantic retriever for the knowledge base.

    The pipeline is optimized for local reuse and fast startup:
    1. Load the KB from `data/kb.txt`.
    2. Split it into overlapping chunks for better semantic coverage.
    3. Embed chunks with Gemini embeddings.
    4. Persist the Chroma vector store to disk.
    5. Reload the persisted store on subsequent runs to avoid re-embedding.
    """
    config = config or get_config()
    kb_path = Path(config.rag.kb_filepath)
    persist_dir = Path(config.rag.vectorstore_path)

    for attempt in range(1, retries + 1):
        try:
            if persist_dir.exists() and any(persist_dir.iterdir()):
                vectorstore = Chroma(
                    collection_name="kb",
                    persist_directory=str(persist_dir),
                    embedding_function=GoogleGenerativeAIEmbeddings(
                        model=config.rag.embeddings_model
                    ),
                )
                logging.info("Loaded persisted RAG vector store from %s", persist_dir)
            else:
                loader = TextLoader(str(kb_path))
                docs = loader.load()
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=config.rag.chunk_size,
                    chunk_overlap=config.rag.chunk_overlap,
                )
                splits = text_splitter.split_documents(docs)

                embeddings = GoogleGenerativeAIEmbeddings(model=config.rag.embeddings_model)
                vectorstore = Chroma.from_documents(
                    documents=splits,
                    embedding=embeddings,
                    collection_name="kb",
                    persist_directory=str(persist_dir),
                )
                vectorstore.persist()
                logging.info(
                    "Built and persisted RAG vector store at %s with %s chunks",
                    persist_dir,
                    len(splits),
                )

            return vectorstore.as_retriever(
                search_kwargs={"k": config.rag.retriever_k}
            )
        except Exception as error:
            logging.warning(
                "Warning: Failed to setup RAG Tool (Attempt %s/%s). Error: %s",
                attempt,
                retries,
                error,
            )
            if attempt < retries:
                time.sleep(2)

    logging.error("RAG Retriever unavailable after retries.")
    return None


def retrieve_kb_snippets(retriever: Any, query: str) -> list[str]:
    """Return the top KB text chunks returned for a query."""
    if retriever is None:
        return []

    if hasattr(retriever, "invoke"):
        docs = retriever.invoke(query)
    elif hasattr(retriever, "get_relevant_documents"):
        docs = retriever.get_relevant_documents(query)
    else:
        raise AttributeError("Retriever does not support invoke() or get_relevant_documents()")

    snippets = []
    for doc in docs:
        text = getattr(doc, "page_content", None) or getattr(doc, "content", None) or str(doc)
        snippets.append(text)
    return snippets


def evaluate_retrieval_examples(retriever: Any, examples: dict[str, str]) -> dict[str, list[str]]:
    """Evaluate retrieval relevance on a set of sample queries."""
    return {label: retrieve_kb_snippets(retriever, query) for label, query in examples.items()}
