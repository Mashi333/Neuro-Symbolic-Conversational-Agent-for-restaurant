from pathlib import Path

import chromadb
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

# Load document
source_path = Path("DataSources/Restaurant Policies.txt")
documents = [
    Document(
        page_content=source_path.read_text(encoding="utf-8"),
        metadata={"source": str(source_path)},
    )
]

# Split text
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50
)

chunks = splitter.split_documents(documents)

# Embedding model
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Create ChromaDB
client = chromadb.PersistentClient(path="./vectordb")
collection = client.get_or_create_collection(name="restaurant_policies")

chunk_texts = [chunk.page_content for chunk in chunks]
chunk_embeddings = embedding_model.embed_documents(chunk_texts)
chunk_ids = [f"chunk-{index}" for index in range(len(chunks))]

collection.upsert(
    ids=chunk_ids,
    documents=chunk_texts,
    embeddings=chunk_embeddings,
    metadatas=[chunk.metadata for chunk in chunks],
)

print("Vector Database Created Successfully!")