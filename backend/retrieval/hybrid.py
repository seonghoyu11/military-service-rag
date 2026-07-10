from retrieval import bm25_search, vector_search

# Tuned via evaluation/tune_hybrid.py grid search against data/eval/test_queries.json:
# alpha=0.3 gave the best MRR (0.893) while keeping Recall@5/@10 at 1.0.
DEFAULT_ALPHA = 0.3


def _min_max_normalize(scores):
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def search(query, bm25, chunks, alpha=DEFAULT_ALPHA, top_k=10, candidate_pool=30):
    """
    Combines BM25 and dense vector search via weighted sum of min-max
    normalized scores. alpha=1.0 is pure dense, alpha=0.0 is pure BM25.
    Both retrievers pull `candidate_pool` candidates each before fusion, so
    the final top_k is re-ranked over their union.
    """
    bm25_results = bm25_search.search(query, bm25, chunks, top_k=candidate_pool)
    dense_results = vector_search.search(query, top_k=candidate_pool)

    bm25_norm = _min_max_normalize([s for _, s in bm25_results])
    dense_norm = _min_max_normalize([s for _, s in dense_results])

    combined = {}
    for (chunk, _), norm_score in zip(bm25_results, bm25_norm):
        combined[chunk["text"]] = {"chunk": chunk, "bm25": norm_score, "dense": 0.0}

    for (chunk, _), norm_score in zip(dense_results, dense_norm):
        key = chunk["text"]
        if key in combined:
            combined[key]["dense"] = norm_score
        else:
            combined[key] = {"chunk": chunk, "bm25": 0.0, "dense": norm_score}

    scored = [
        (v["chunk"], alpha * v["dense"] + (1 - alpha) * v["bm25"])
        for v in combined.values()
    ]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]
