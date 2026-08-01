"""
LangChain-compatible Embeddings wrapper around this project's own BGE-m3
loader (pipeline/embedder.py), for RAGAS's answer_relevancy metric (which
needs embeddings to compare the generated answer's implied question against
the real one).

Deliberately NOT using a Gemini embedding API here, even though it would
also be free-tier -- BGE-m3 runs locally (same model already loaded for
retrieval), so this metric makes zero network calls and can't touch any
quota, Gemini or otherwise.
"""
from typing import List

from pipeline.embedder import embed_passages, embed_queries


class BGE_M3_Embeddings:
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return embed_passages("bge-m3", texts).tolist()

    def embed_query(self, text: str) -> List[float]:
        return embed_queries("bge-m3", [text])[0].tolist()

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        # BGE-m3 runs locally via sentence-transformers, which is
        # synchronous-only -- there's no real async path to defer to, so
        # this just calls the sync version directly.
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return self.embed_query(text)
