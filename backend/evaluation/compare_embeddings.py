import os
import sys
import json
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.embedder import MODEL_CONFIGS, embed_passages, embed_queries

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_PATH = os.path.join(BACKEND_DIR, "data", "processed", "law_chunks.json")
QUERIES_PATH = os.path.join(BACKEND_DIR, "data", "eval", "test_queries.json")
RESULTS_PATH = os.path.join(BACKEND_DIR, "data", "eval", "embedding_comparison_results.json")

TOP_KS = [5, 10]


def chunk_matches(chunk, relevant):
    if chunk["law_name"] != relevant["law_name"]:
        return False
    if chunk["article_no"] != relevant["article_no"]:
        return False
    expected_para = relevant.get("paragraph_no")
    if expected_para is None:
        return True
    return chunk["paragraph_no"] == expected_para


def evaluate_model(model_key, chunks, queries):
    print(f"\n--- Embedding with {model_key} ({MODEL_CONFIGS[model_key]['model_name']}) ---")
    chunk_texts = [c["text"] for c in chunks]
    chunk_vecs = embed_passages(model_key, chunk_texts)

    positive_queries = [q for q in queries if q["relevant_chunks"]]
    negative_queries = [q for q in queries if not q["relevant_chunks"]]

    query_texts = [q["question"] for q in queries]
    query_vecs = embed_queries(model_key, query_texts)

    sims = query_vecs @ chunk_vecs.T  # cosine similarity, vectors are normalized

    per_query_results = []
    recall_hits = {k: 0 for k in TOP_KS}
    mrr_total = 0.0

    for qi, q in enumerate(queries):
        order = np.argsort(-sims[qi])
        ranked_chunks = [chunks[i] for i in order]
        ranked_scores = sims[qi][order]

        if q["relevant_chunks"]:
            rank_of_first_hit = None
            for rank, c in enumerate(ranked_chunks, start=1):
                if any(chunk_matches(c, rc) for rc in q["relevant_chunks"]):
                    rank_of_first_hit = rank
                    break

            for k in TOP_KS:
                if rank_of_first_hit is not None and rank_of_first_hit <= k:
                    recall_hits[k] += 1
            mrr_total += (1.0 / rank_of_first_hit) if rank_of_first_hit else 0.0

            per_query_results.append({
                "id": q["id"], "question": q["question"], "rank_of_first_hit": rank_of_first_hit,
                "top1_score": float(ranked_scores[0]),
            })
        else:
            # Negative (out-of-scope) query: no recall to compute, just record top score for eyeballing
            per_query_results.append({
                "id": q["id"], "question": q["question"], "rank_of_first_hit": None,
                "top1_score": float(ranked_scores[0]),
                "top1_chunk": f"{ranked_chunks[0]['law_name']} {ranked_chunks[0]['article_no']}",
            })

    n_pos = len(positive_queries)
    summary = {
        "model_key": model_key,
        "model_name": MODEL_CONFIGS[model_key]["model_name"],
        "recall_at_k": {k: round(recall_hits[k] / n_pos, 3) for k in TOP_KS},
        "mrr": round(mrr_total / n_pos, 3),
        "avg_negative_top1_score": round(
            float(np.mean([r["top1_score"] for r in per_query_results if r["rank_of_first_hit"] is None])), 3
        ) if negative_queries else None,
        "avg_positive_top1_score": round(
            float(np.mean([r["top1_score"] for r in per_query_results if r["rank_of_first_hit"] is not None])), 3
        ),
        "per_query": per_query_results,
    }
    return summary


def main():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    with open(QUERIES_PATH, encoding="utf-8") as f:
        queries = json.load(f)

    print(f"Loaded {len(chunks)} chunks, {len(queries)} test queries.")

    all_results = []
    for model_key in MODEL_CONFIGS:
        result = evaluate_model(model_key, chunks, queries)
        all_results.append(result)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("EMBEDDING MODEL COMPARISON")
    print("=" * 70)
    header = f"{'model':<24} {'Recall@5':>10} {'Recall@10':>10} {'MRR':>8} {'neg_top1':>10}"
    print(header)
    for r in all_results:
        print(f"{r['model_key']:<24} {r['recall_at_k'][5]:>10} {r['recall_at_k'][10]:>10} {r['mrr']:>8} {str(r['avg_negative_top1_score']):>10}")
    print(f"\nFull per-query results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
