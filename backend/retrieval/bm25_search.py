from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi

# Content-bearing POS tags only: nouns, numbers, verb/adjective stems, foreign
# words. Drops particles (J*) and endings (E*), which just add noise to a
# Korean BM25 index since they attach to almost every word.
CONTENT_POS_PREFIXES = ("NNG", "NNP", "NNB", "NR", "NP", "VV", "VA", "VX", "SL", "SN")

_kiwi = Kiwi()


def tokenize(text):
    return [t.form for t in _kiwi.tokenize(text) if t.tag.startswith(CONTENT_POS_PREFIXES)]


def build_bm25_index(chunks):
    """Builds a BM25 index over chunk texts. Returns (bm25, tokenized_corpus)."""
    tokenized_corpus = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    return bm25


def search(query, bm25, chunks, top_k=10):
    """Returns the top_k (chunk, score) pairs for a query, ranked by BM25 score."""
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(chunks)), key=lambda i: -scores[i])[:top_k]
    return [(chunks[i], float(scores[i])) for i in ranked]
