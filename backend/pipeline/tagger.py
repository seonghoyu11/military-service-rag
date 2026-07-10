from classifier.model import USER_TYPE_KEYWORDS, TOPIC_KEYWORDS


def tag_chunk(chunk):
    """
    Applies metadata tags to a single law chunk, using the same keyword
    tables as classifier/predict.py so chunk tags and query intent stay on
    the same vocabulary for future tag-filtered retrieval.
    If no user tags match, defaults to ["전체"].
    If no topic tags match, defaults to ["일반"].
    """
    text = chunk["text"]
    title = chunk["article_title"]

    # Create search space combining the title and the body content (case-insensitive search)
    search_space = f"{title} {text}".lower()

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

    chunk["user_type_tags"] = user_type_tags
    chunk["topic_tags"] = topic_tags

    return chunk

def tag_chunks(chunks):
    """
    Applies tagging to a list of chunks in place.
    """
    for chunk in chunks:
        tag_chunk(chunk)
    return chunks