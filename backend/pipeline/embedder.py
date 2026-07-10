from sentence_transformers import SentenceTransformer

# E5-family models require "query: " / "passage: " prefixes on the input text
# (this is baked into how they were trained, not optional). BGE-m3 doesn't
# need either prefix for retrieval.
MODEL_CONFIGS = {
    "bge-m3": {
        "model_name": "BAAI/bge-m3",
        "query_prefix": "",
        "passage_prefix": "",
    },
    "multilingual-e5-large": {
        "model_name": "intfloat/multilingual-e5-large",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
    "koe5": {
        "model_name": "nlpai-lab/KoE5",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
}

_loaded_models = {}


def load_model(model_key):
    """Loads (and caches) a SentenceTransformer model by its MODEL_CONFIGS key."""
    if model_key not in _loaded_models:
        model_name = MODEL_CONFIGS[model_key]["model_name"]
        _loaded_models[model_key] = SentenceTransformer(model_name)
    return _loaded_models[model_key]


def embed_passages(model_key, texts, batch_size=16):
    """Embeds document/chunk texts using the model's passage-side convention."""
    model = load_model(model_key)
    prefix = MODEL_CONFIGS[model_key]["passage_prefix"]
    prefixed = [f"{prefix}{t}" for t in texts]
    return model.encode(prefixed, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=True)


def embed_queries(model_key, texts, batch_size=16):
    """Embeds user queries using the model's query-side convention."""
    model = load_model(model_key)
    prefix = MODEL_CONFIGS[model_key]["query_prefix"]
    prefixed = [f"{prefix}{t}" for t in texts]
    return model.encode(prefixed, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=True)
