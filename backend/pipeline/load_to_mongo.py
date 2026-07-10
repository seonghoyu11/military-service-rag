import os
import sys
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo.operations import SearchIndexModel
from db.mongo import get_db
from pipeline.embedder import embed_passages

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_PATH = os.path.join(BACKEND_DIR, "data", "processed", "law_chunks.json")

MODEL_KEY = "bge-m3"
EMBEDDING_DIM = 1024
COLLECTION_NAME = "law_chunks"
VECTOR_INDEX_NAME = "law_chunks_vector_index"


def load_chunks_with_embeddings(collection):
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Embedding {len(chunks)} chunks with {MODEL_KEY}...")
    vectors = embed_passages(MODEL_KEY, [c["text"] for c in chunks])

    docs = []
    for chunk, vector in zip(chunks, vectors):
        doc = dict(chunk)
        doc["embedding"] = vector.tolist()
        docs.append(doc)

    print(f"Clearing existing '{COLLECTION_NAME}' collection...")
    collection.delete_many({})

    print(f"Inserting {len(docs)} documents...")
    collection.insert_many(docs)


def ensure_vector_index(collection):
    existing = list(collection.list_search_indexes())
    if any(idx["name"] == VECTOR_INDEX_NAME for idx in existing):
        print(f"Vector index '{VECTOR_INDEX_NAME}' already exists, dropping it first for a clean rebuild...")
        collection.drop_search_index(VECTOR_INDEX_NAME)
        # Wait for the drop to take effect before recreating with the same name
        while any(idx["name"] == VECTOR_INDEX_NAME for idx in collection.list_search_indexes()):
            time.sleep(2)

    print(f"Creating Atlas Vector Search index '{VECTOR_INDEX_NAME}'...")
    search_index_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIM,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "user_type_tags"},
                {"type": "filter", "path": "topic_tags"},
            ]
        },
        name=VECTOR_INDEX_NAME,
        type="vectorSearch",
    )
    collection.create_search_index(model=search_index_model)

    print("Waiting for index to build (this can take a minute on Atlas)...")
    while True:
        indexes = list(collection.list_search_indexes(VECTOR_INDEX_NAME))
        if indexes and indexes[0].get("queryable"):
            break
        time.sleep(5)
    print("Vector index is queryable.")


def main():
    db = get_db()
    collection = db[COLLECTION_NAME]

    load_chunks_with_embeddings(collection)
    ensure_vector_index(collection)

    print(f"\nDone. '{COLLECTION_NAME}' has {collection.count_documents({})} documents with embeddings + a queryable vector index.")


if __name__ == "__main__":
    main()
