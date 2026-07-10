from classifier.model import USER_TYPE_KEYWORDS, TOPIC_KEYWORDS, POSTPONEMENT_CANCEL_PATTERN


def _body_only(text):
    """Strips the leading '[법명 제N조(제목) 항]' header so title text (which
    can itself contain words like '취소', e.g. 병역법 70조 "국외여행의 허가 및
    취소") doesn't leak into every paragraph's directional-tag detection."""
    parts = text.split("]\n", 1)
    return parts[1] if len(parts) > 1 else text


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

    # Directional split: is this paragraph about GRANTING a postponement, or
    # CANCELLING one that was already granted? See classifier/model.py for why
    # plain "취소" co-occurrence isn't precise enough here.
    #
    # 국외여행 업무처리 규정 제24조 (영주권자 등 입영희망신청제도 운영) is
    # unconditionally forced to "입영연기_취소": the whole article is about
    # voluntarily giving up an existing postponement to enlist early, but not
    # every paragraph mentions "연기" or "취소" at all (e.g. 제8항 is just a
    # resubmission-timing rule) -- gating this on "연기" already being in
    # topic_tags let those paragraphs slip through with no directional tag at
    # all, so routes/query.py's boost/penalty never touched them and they
    # ranked on raw reranker score alone. Scoped to this exact article (not a
    # generic "입영희망" title match) so it doesn't also catch 시행령
    # 제135조의2 (현역 등 입영희망자의 처리), a same-titled but unrelated
    # domestic reclassification provision.
    is_voluntary_early_enlistment_article = (
        chunk.get("law_name") == "병역의무자 국외여행 업무처리 규정" and chunk.get("article_no") == "24"
    )
    if is_voluntary_early_enlistment_article:
        if "연기" not in topic_tags:
            topic_tags.append("연기")
        topic_tags.append("입영연기_취소")
    elif "연기" in topic_tags:
        if POSTPONEMENT_CANCEL_PATTERN.search(_body_only(text)):
            topic_tags.append("입영연기_취소")
        else:
            topic_tags.append("입영연기_신청")

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