from db.mongo import get_db
from pipeline.embedder import embed_queries

COLLECTION_NAME = "law_chunks"
VECTOR_INDEX_NAME = "law_chunks_vector_index"
MODEL_KEY = "bge-m3"


def search(query, top_k=10, num_candidates=100):
    """Returns the top_k (chunk, score) pairs for a query via Atlas $vectorSearch."""
    collection = get_db()[COLLECTION_NAME]
    query_vector = embed_queries(MODEL_KEY, [query])[0].tolist()

    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "embedding": 0,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results = []
    for doc in collection.aggregate(pipeline):
        score = doc.pop("score")
        results.append((doc, score))
    return results
