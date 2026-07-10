from classifier.model import (
    USER_TYPE_KEYWORDS,
    TOPIC_KEYWORDS,
    OUT_OF_SCOPE_KEYWORDS,
    OUT_OF_SCOPE_FALLBACK_MESSAGE,
)


def classify(question):
    """
    Rule-based intent classification for an incoming user question.
    Returns user_type_tags/topic_tags (same vocabulary as pipeline/tagger.py,
    so they line up with chunk metadata for future filtered retrieval), plus
    an out_of_scope flag for topics deliberately excluded from the dataset.
    """
    search_space = question.lower()

    if any(kw in search_space for kw in OUT_OF_SCOPE_KEYWORDS):
        return {
            "user_type_tags": [],
            "topic_tags": [],
            "out_of_scope": True,
            "fallback_message": OUT_OF_SCOPE_FALLBACK_MESSAGE,
        }

    user_type_tags = [
        tag for tag, keywords in USER_TYPE_KEYWORDS.items()
        if any(kw in search_space for kw in keywords)
    ]
    if not user_type_tags:
        user_type_tags = ["전체"]

    topic_tags = [
        tag for tag, keywords in TOPIC_KEYWORDS.items()
        if any(kw in search_space for kw in keywords)
    ]
    if not topic_tags:
        topic_tags = ["일반"]

    return {
        "user_type_tags": user_type_tags,
        "topic_tags": topic_tags,
        "out_of_scope": False,
        "fallback_message": None,
    }