from sentence_transformers import CrossEncoder

MODEL_NAME = "BAAI/bge-reranker-v2-m3"

_model = None


def _get_model():
    global _model
    if _model is None:
        # CPU is plenty fast for reranking a few dozen candidates, and avoids
        # the extra memory pressure of loading onto MPS alongside everything
        # else already resident (embedding model, MongoDB client, etc).
        _model = CrossEncoder(MODEL_NAME, device="cpu")
    return _model


def preload():
    """Forces the reranker weights to load now. See app.py's _preload_models."""
    _get_model()


def rerank(query, candidates, top_k=5):
    """
    candidates: list of (chunk, score) tuples, e.g. hybrid.search() output.
    Returns the top_k (chunk, rerank_score) pairs, re-sorted by cross-encoder
    relevance score (candidates' original scores are ignored).
    """
    if not candidates:
        return []
    model = _get_model()
    pairs = [(query, chunk["text"]) for chunk, _ in candidates]
    scores = model.predict(pairs)
    reranked = sorted(zip((c for c, _ in candidates), scores), key=lambda x: -x[1])
    return [(chunk, float(score)) for chunk, score in reranked[:top_k]]