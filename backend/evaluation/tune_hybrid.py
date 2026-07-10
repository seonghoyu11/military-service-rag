import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval import bm25_search, hybrid

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_PATH = os.path.join(BACKEND_DIR, "data", "processed", "law_chunks.json")
QUERIES_PATH = os.path.join(BACKEND_DIR, "data", "eval", "test_queries.json")
RESULTS_PATH = os.path.join(BACKEND_DIR, "data", "eval", "hybrid_alpha_grid_results.json")

TOP_KS = [5, 10]
ALPHAS = [round(a * 0.1, 1) for a in range(0, 11)]  # 0.0, 0.1, ..., 1.0


def chunk_matches(chunk, relevant):
    if chunk["law_name"] != relevant["law_name"]:
        return False
    if chunk["article_no"] != relevant["article_no"]:
        return False
    expected_para = relevant.get("paragraph_no")
    if expected_para is None:
        return True
    return chunk["paragraph_no"] == expected_para


def evaluate_alpha(alpha, bm25, chunks, queries):
    positive_queries = [q for q in queries if q["relevant_chunks"]]
    recall_hits = {k: 0 for k in TOP_KS}
    mrr_total = 0.0

    for q in queries:
        results = hybrid.search(q["question"], bm25, chunks, alpha=alpha, top_k=max(TOP_KS), candidate_pool=30)
        if not q["relevant_chunks"]:
            continue

        rank = None
        for r, (c, _) in enumerate(results, start=1):
            if any(chunk_matches(c, rc) for rc in q["relevant_chunks"]):
                rank = r
                break

        for k in TOP_KS:
            if rank is not None and rank <= k:
                recall_hits[k] += 1
        mrr_total += (1.0 / rank) if rank else 0.0

    n_pos = len(positive_queries)
    return {
        "alpha": alpha,
        "recall_at_k": {k: round(recall_hits[k] / n_pos, 3) for k in TOP_KS},
        "mrr": round(mrr_total / n_pos, 3),
    }


def main():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    with open(QUERIES_PATH, encoding="utf-8") as f:
        queries = json.load(f)

    print(f"Loaded {len(chunks)} chunks, {len(queries)} test queries.")
    print("Building BM25 index...")
    bm25 = bm25_search.build_bm25_index(chunks)

    results = []
    for alpha in ALPHAS:
        r = evaluate_alpha(alpha, bm25, chunks, queries)
        results.append(r)
        print(f"alpha={alpha:.1f}  Recall@5={r['recall_at_k'][5]:.3f}  Recall@10={r['recall_at_k'][10]:.3f}  MRR={r['mrr']:.3f}")

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    best = max(results, key=lambda r: (r["recall_at_k"][5], r["mrr"]))
    print(f"\nBest alpha: {best['alpha']} -> {best}")
    print(f"Full grid saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
