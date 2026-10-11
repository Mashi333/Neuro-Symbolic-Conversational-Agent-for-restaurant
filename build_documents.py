"""Step 4 - Convert relational database records into documents.

Turns every row of restaurant_conversational_agent_db.sql plus the free-text
knowledge files into LangChain Document objects ready for chunking,
embedding and loading into the Chroma vector database.

Outputs: DataSources/documents.jsonl (one JSON object per document)

Run:  python build_documents.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from retrieve import DATA_DIR, load_structured_data

OUTPUT_PATH = DATA_DIR / "documents.jsonl"

TEXT_SOURCES = (
    "Restaurant Policies.txt",
    "Discount Policies.txt",
    "Restaurant FAQs.txt",
    "Allergy Guidelines.txt",
    "Restaurant Descriptions.txt",
    "Customer Reviews.txt",
)

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


def _price(value: object) -> str:
    return f"${float(value):.2f}"


def menu_item_documents(data: dict[str, object]) -> list[Document]:
    documents: list[Document] = []
    item_allergens: dict[int, list[str]] = data["item_allergens"]  # type: ignore[assignment]
    item_dietary: dict[int, list[str]] = data["item_dietary"]  # type: ignore[assignment]
    item_ingredients: dict[int, list[str]] = data["item_ingredients"]  # type: ignore[assignment]

    for item_id, item in sorted(data["menu_items_by_id"].items()):  # type: ignore[union-attr]
        allergens = item_allergens.get(int(item_id), [])
        dietary = item_dietary.get(int(item_id), [])
        ingredients = item_ingredients.get(int(item_id), [])

        lines = [
            f"Menu item: {item['item_name']}",
            f"Category: {item.get('category') or 'Other'}",
            f"Description: {item.get('description') or 'No description'}",
            f"Price: {_price(item['price'])}",
            f"Calories: {int(float(item['calories']))} kcal",
        ]
        if ingredients:
            lines.append(f"Ingredients: {', '.join(sorted(ingredients))}")
        if allergens:
            lines.append(f"Contains allergens: {', '.join(sorted(allergens))}")
        else:
            lines.append("Contains allergens: None declared")
        if dietary:
            lines.append(f"Dietary tags: {', '.join(sorted(dietary))}")

        documents.append(
            Document(
                page_content="\n".join(lines),
                metadata={
                    "doc_type": "menu_item",
                    "item_id": int(item_id),
                    "item_name": str(item["item_name"]),
                    "category": str(item.get("category") or "Other"),
                    "source": "restaurant_conversational_agent_db.sql",
                },
            )
        )
    return documents


def policy_documents(data: dict[str, object]) -> list[Document]:
    documents: list[Document] = []
    for row in data["restaurant_policies"]:  # type: ignore[union-attr]
        documents.append(
            Document(
                page_content=f"{row['policy_name']}: {row['policy_description']}",
                metadata={
                    "doc_type": "policy",
                    "policy_id": int(row["policy_id"]),
                    "policy_name": str(row["policy_name"]),
                    "source": "restaurant_conversational_agent_db.sql",
                },
            )
        )
    return documents


def text_file_documents() -> list[Document]:
    documents: list[Document] = []
    for name in TEXT_SOURCES:
        path = DATA_DIR / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        for piece_index, piece in enumerate(
            splitter.split_text(text) if len(text) > CHUNK_SIZE else [text]
        ):
            documents.append(
                Document(
                    page_content=piece,
                    metadata={
                        "doc_type": "knowledge_text",
                        "source": name,
                        "chunk": piece_index,
                    },
                )
            )
    return documents


def build_documents() -> list[Document]:
    data = load_structured_data()
    documents = (
        menu_item_documents(data)
        + policy_documents(data)
        + text_file_documents()
    )

    seen: set[str] = set()
    unique: list[Document] = []
    for index, doc in enumerate(documents):
        content = doc.page_content.strip()
        if not content:
            raise ValueError(f"empty document at index {index}: {doc.metadata}")
        doc_id = json.dumps([doc.metadata, content], sort_keys=True)
        if doc_id in seen:
            continue
        seen.add(doc_id)
        doc.metadata["doc_id"] = f"doc-{len(unique):04d}"
        unique.append(doc)
    return unique


def write_jsonl(documents: list[Document], path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for doc in documents:
            record = {
                "id": doc.metadata["doc_id"],
                "page_content": doc.page_content,
                "metadata": doc.metadata,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert DB records to documents")
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH, help="JSONL output path")
    args = parser.parse_args()

    documents = build_documents()
    write_jsonl(documents, args.out)

    by_type: dict[str, int] = {}
    for doc in documents:
        doc_type = str(doc.metadata["doc_type"])
        by_type[doc_type] = by_type.get(doc_type, 0) + 1

    print(f"Wrote {len(documents)} documents to {args.out}")
    for doc_type in sorted(by_type):
        print(f"  {doc_type}: {by_type[doc_type]}")


if __name__ == "__main__":
    main()
