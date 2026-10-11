"""Step 8 - Basic semantic retrieval (RAG retrieval, tested on its own).

The pipeline, with no LLM and no ASP rules:

    user query
      -> embedding vector (sentence-transformers/all-MiniLM-L6-v2)
      -> vector search in ChromaDB (cosine similarity)
      -> top-K documents, ranked by similarity score

The index is built once from DataSources/documents.jsonl (step 4 output)
and stored in ./vectordb, so later runs only embed the query.

Run examples:
    python semantic_retrieval.py "I want a cheap vegetarian meal."
    python semantic_retrieval.py "peanut allergy safe dishes" -k 3
    python semantic_retrieval.py "reservation policy" --type all
    python semantic_retrieval.py "..." --rebuild     # rebuild the index
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings

from retrieve import BASE_DIR

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "restaurant_knowledge"
VECTOR_DIR = BASE_DIR / "vectordb"
DOCUMENTS_PATH = BASE_DIR / "DataSources" / "documents.jsonl"


@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """Load the embedding model once and reuse it for every query."""
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def _get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(VECTOR_DIR))


def load_documents() -> list[dict]:
    """Read the documents produced by build_documents.py (step 4)."""
    if not DOCUMENTS_PATH.exists():
        from build_documents import build_documents, write_jsonl

        write_jsonl(build_documents(), DOCUMENTS_PATH)

    with DOCUMENTS_PATH.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_index(force: bool = False) -> chromadb.Collection:
    """Embed every document once and store it in the vector database."""
    client = _get_client()

    if force:
        existing = {getattr(col, "name", col) for col in client.list_collections()}
        if COLLECTION_NAME in existing:
            client.delete_collection(COLLECTION_NAME)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    documents = load_documents()
    if collection.count() != len(documents):
        client.delete_collection(COLLECTION_NAME)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        model = get_embedding_model()
        contents = [doc["page_content"] for doc in documents]
        embeddings = model.embed_documents(contents)
        collection.upsert(
            ids=[doc["id"] for doc in documents],
            documents=contents,
            embeddings=embeddings,
            metadatas=[doc["metadata"] for doc in documents],
        )
    return collection


def semantic_search(
    query: str,
    k: int = 5,
    doc_type: str | None = "menu_item",
) -> list[dict]:
    """Embed the query and return the top-K most similar documents.

    Each result: {rank, score, distance, content, metadata}.
    score = 1 - cosine_distance, so 1.0 means identical meaning.
    """
    collection = build_index()

    query_embedding = get_embedding_model().embed_query(query)

    where = None
    if doc_type and doc_type != "all":
        where = {"doc_type": {"$eq": doc_type}}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    matches: list[dict] = []
    for index, (content, metadata, distance) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ),
        start=1,
    ):
        matches.append(
            {
                "rank": index,
                "score": 1.0 - distance,
                "distance": distance,
                "content": content,
                "metadata": metadata,
            }
        )
    return matches


def _content_field(content: str, field: str) -> str | None:
    """Read a 'Field: value' line out of a generated document."""
    prefix = f"{field}: "
    for line in content.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def format_result(match: dict) -> str:
    metadata = match["metadata"]
    doc_type = metadata.get("doc_type", "?")
    name = metadata.get("item_name") or metadata.get("policy_name")
    source = metadata.get("source", "")
    content = match["content"]

    title = name or source
    lines = [
        f"{match['rank']}. similarity={match['score']:.4f} | {doc_type} | {title}",
    ]

    if doc_type == "menu_item":
        category = _content_field(content, "Category") or "-"
        price = _content_field(content, "Price") or "-"
        calories = _content_field(content, "Calories") or "-"
        description = _content_field(content, "Description") or "-"
        lines.append(f"   Category: {category} | Price: {price} | Calories: {calories}")
        lines.append(f"   Description: {description}")
        for field in ("Dietary tags", "Contains allergens", "Ingredients"):
            value = _content_field(content, field)
            if value:
                lines.append(f"   {field}: {value}")
    else:
        for line in content.splitlines()[:3]:
            lines.append(f"   {line}")
        lines.append(f"   Source: {source}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic retrieval over the restaurant data")
    parser.add_argument("query", help="user query to search for")
    parser.add_argument("-k", type=int, default=5, help="number of results (default 5)")
    parser.add_argument(
        "--type",
        default="menu_item",
        choices=["menu_item", "policy", "knowledge_text", "all"],
        help="which document type to search (default menu_item)",
    )
    parser.add_argument("--rebuild", action="store_true", help="rebuild the vector index")
    args = parser.parse_args()

    collection = build_index(force=args.rebuild)

    print(f'Query: "{args.query}"')
    print(
        f"Index: {collection.name} | {collection.count()} documents | "
        f"model: {EMBEDDING_MODEL} | type filter: {args.type}"
    )
    print()

    matches = semantic_search(args.query, k=args.k, doc_type=args.type)
    if not matches:
        print("No results.")
        return

    print(f"Top {len(matches)} results:")
    for match in matches:
        print(format_result(match))
        print()


if __name__ == "__main__":
    main()
