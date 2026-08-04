import hashlib
import os
import sys

from flask import Flask
from flask_cors import CORS

from routes import query as query_module
from routes import profile as profile_module
from routes import feedback as feedback_module
from classifier.model import POST_SERVICE_KEYWORDS
from pipeline.embedder import load_model as load_embedder_model
from retrieval import reranker as reranker_module


def _log_startup_fingerprint():
    """
    Prints what this process actually loaded -- chunk count/mtime and a
    classifier-keyword fingerprint -- so a stale/orphaned process (old code
    still being served after a restart that didn't fully take) shows up in
    the log instead of silently serving outdated behavior. See
    docs/eval_results.md "배포 동기화 이슈".
    """
    chunks_path = query_module.CHUNKS_PATH
    chunk_count = len(query_module._chunks)
    mtime = os.path.getmtime(chunks_path)

    keywords_repr = repr(sorted(POST_SERVICE_KEYWORDS)).encode("utf-8")
    keywords_hash = hashlib.sha256(keywords_repr).hexdigest()[:8]

    print(
        f"[startup] pid={os.getpid()} law_chunks.json: {chunk_count} chunks, "
        f"mtime={mtime:.0f} | POST_SERVICE_KEYWORDS: {len(POST_SERVICE_KEYWORDS)} "
        f"keywords, hash={keywords_hash}",
        file=sys.stderr,
    )


def _preload_models():
    """
    Forces the embedder/reranker weights to load now instead of on whichever
    request happens to be the first in-scope query the process sees. Without
    this, that unlucky request eats the full model-load cost inline (BGE-m3 +
    bge-reranker-v2-m3 both loading lazily add several seconds) -- see
    docs/eval_results.md "cold-start on first in-scope query".
    """
    import time

    t0 = time.time()
    load_embedder_model("bge-m3")
    reranker_module.preload()
    print(f"[startup] models preloaded in {time.time() - t0:.2f}s", file=sys.stderr)


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(query_module.query_bp)
    app.register_blueprint(profile_module.profile_bp)
    app.register_blueprint(feedback_module.feedback_bp)
    return app


app = create_app()
_preload_models()
_log_startup_fingerprint()

if __name__ == "__main__":
    app.run(debug=True, port=5001)