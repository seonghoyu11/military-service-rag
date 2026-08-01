from classifier.model import (
    USER_TYPE_KEYWORDS,
    TOPIC_KEYWORDS,
    OUT_OF_SCOPE_KEYWORDS,
    OUT_OF_SCOPE_CATEGORIES,
    OUT_OF_SCOPE_BASE_MESSAGE,
    OUT_OF_SCOPE_KATUSA_LANGUAGE_RELATION_NOTE,
    OUT_OF_SCOPE_RELATED_LOOKUP,
    OUT_OF_SCOPE_GUIDANCE_WITH_USER_TYPE,
    OUT_OF_SCOPE_GUIDANCE_GENERIC,
    POSTPONEMENT_CANCEL_QUERY_KEYWORDS,
    POST_SERVICE_KEYWORDS,
    POST_SERVICE_FALLBACK_MESSAGE,
    SYNONYM_ANCHOR_LOOKUPS,
)


def _detect_user_types(search_space):
    return [
        tag for tag, keywords in USER_TYPE_KEYWORDS.items()
        if any(kw in search_space for kw in keywords)
    ]


def _out_of_scope_message(search_space):
    """Points to the specific MMA recruitment-notice page(s) the question
    matched, instead of a generic "go check mma.go.kr" shrug. Independently
    checks every category (not if/elif), so a question mentioning multiple
    programs gets every matching link, not just the first one found."""
    links = [
        (name, category["url"])
        for name, category in OUT_OF_SCOPE_CATEGORIES.items()
        if category["url"] and any(kw in search_space for kw in category["keywords"])
    ]

    if not links:
        return f"{OUT_OF_SCOPE_BASE_MESSAGE} 정확한 기준은 병무청 홈페이지(mma.go.kr) 모집공고를 확인해 주세요."

    link_lines = "\n".join(f"- {name}: {url}" for name, url in links)
    message = f"{OUT_OF_SCOPE_BASE_MESSAGE} 정확한 기준은 아래 병무청 모집공고를 확인해 주세요.\n{link_lines}"

    matched_names = {name for name, _ in links}
    if {"카투사", "어학병"} <= matched_names:
        message += f"\n\n{OUT_OF_SCOPE_KATUSA_LANGUAGE_RELATION_NOTE}"

    return message


def _detect_anchor_lookups(search_space):
    """Returns the (law_name, article_no) lookups whose trigger keywords
    appear in the question, for routes/query.py to force into the candidate
    pool regardless of BM25/dense rank -- see SYNONYM_ANCHOR_LOOKUPS."""
    return [
        {"law_name": anchor["law_name"], "article_no": anchor["article_no"]}
        for anchor in SYNONYM_ANCHOR_LOOKUPS
        if any(kw in search_space for kw in anchor["keywords"])
    ]


def classify(question, session_user_type=None):
    """
    Rule-based intent classification for an incoming user question.
    Returns user_type_tags/topic_tags (same vocabulary as pipeline/tagger.py,
    so they line up with chunk metadata for future filtered retrieval), plus
    an out_of_scope flag for topics deliberately excluded from the dataset.

    session_user_type: the caller's saved profile (Stage 6 /api/profile),
    used as a fallback ONLY when the question itself has no user-type signal
    -- a question can be about a third party, so anything `_detect_user_types`
    actually finds in the text always wins over the session default. This is
    a pure UX convenience (skip re-typing "저는 영주권자인데..." every time);
    it doesn't feed into retrieval ranking at all (see routes/query.py), only
    the OOS message and the intent tags shown to the user.
    """
    search_space = question.lower()
    session_fallback = [session_user_type] if session_user_type else []

    # Checked before the MMA-recruitment out-of-scope category: same
    # "out of scope" outcome, but for a structurally different reason (no
    # data at all vs. a yearly-changing notice), so it needs its own message
    # rather than being folded into the MMA-link framing.
    if any(kw in search_space for kw in POST_SERVICE_KEYWORDS):
        return {
            "user_type_tags": _detect_user_types(search_space) or session_fallback,
            "topic_tags": [],
            "out_of_scope": True,
            "fallback_message": POST_SERVICE_FALLBACK_MESSAGE,
            "related_lookup": None,
            "anchor_lookups": [],
        }

    if any(kw in search_space for kw in OUT_OF_SCOPE_KEYWORDS):
        user_type_tags = _detect_user_types(search_space) or session_fallback

        if user_type_tags:
            guidance = OUT_OF_SCOPE_GUIDANCE_WITH_USER_TYPE.format(
                user_types="/".join(user_type_tags)
            )
            related_lookup = OUT_OF_SCOPE_RELATED_LOOKUP
        else:
            guidance = OUT_OF_SCOPE_GUIDANCE_GENERIC
            related_lookup = None

        return {
            "user_type_tags": user_type_tags,
            "topic_tags": [],
            "out_of_scope": True,
            "fallback_message": f"{_out_of_scope_message(search_space)}\n\n{guidance}",
            "related_lookup": related_lookup,
            "anchor_lookups": [],
        }

    user_type_tags = _detect_user_types(search_space) or session_fallback or ["전체"]

    topic_tags = [
        tag for tag, keywords in TOPIC_KEYWORDS.items()
        if any(kw in search_space for kw in keywords)
    ]
    if not topic_tags:
        topic_tags = ["일반"]

    # Directional split, same idea as pipeline/tagger.py: default to "wants to
    # get a postponement" unless the question itself signals cancellation --
    # users describe cancelling very differently from the statute, so this
    # uses plain negation cues instead of the statute regex.
    if "연기" in topic_tags:
        if any(kw in search_space for kw in POSTPONEMENT_CANCEL_QUERY_KEYWORDS):
            topic_tags.append("입영연기_취소")
        else:
            topic_tags.append("입영연기_신청")

    return {
        "user_type_tags": user_type_tags,
        "topic_tags": topic_tags,
        "out_of_scope": False,
        "fallback_message": None,
        "related_lookup": None,
        "anchor_lookups": _detect_anchor_lookups(search_space),
    }