# Rule-based keyword tables shared by the intent classifier (query-side) and
# the chunk tagger (corpus-side), so both stay in sync on what each tag means.
# Swap in a lightweight trained classifier here once enough labeled query data
# has accumulated (see project plan, stage 4).

import re

# Directional split of the "연기" umbrella topic. A chunk/query about the
# postponement MECHANISM ("국외여행허가를 받으면 연기된 것으로 본다") is the
# opposite of one about CANCELLING an already-granted postponement (e.g. 영주권자
# 등 입영희망신청으로 자진 입대하면서 기존 연기 처분을 취소하는 경우) -- conflating
# them under one "연기" tag let a "취소" chunk outrank the real answer.
#
# Corpus side: only match the specific statute phrasing for revoking a granted
# postponement itself ("연기를 취소", "연기처분을 취소", "입영등 연기의 취소" ...).
# Plain co-occurrence of "연기" and "취소" in the same chunk is too broad --
# many chunks (병역법 70조 전체, 147조의2, 시행규칙 99조 등) mention "허가취소"
# (a travel permit being revoked as a penalty), a related but different act.
POSTPONEMENT_CANCEL_PATTERN = re.compile(r'연기\s*(를|처분을|처분의|처분과|의)?\s*.{0,25}?취소')

# Query side: users don't phrase cancellation the way the statute does, so
# match plain negation/cancellation cues instead of the statute regex.
# "자진"/"조기" belong here too -- volunteering for early enlistment (병역의무자
# 국외여행 업무처리 규정 제24조, 영주권자 등 입영희망신청제도) means giving up an
# existing/potential postponement, same direction as an explicit "취소".
#
# Deliberately NOT a bare "취소"/"철회" -- "입영연기가 취소되나요" (passive,
# asking whether it WILL be cancelled, e.g. as a side-effect of taking a leave
# of absence) is a "_신청"-side question, not a "_취소"-side one. Only match
# phrasings that express the user's own active intent to cancel/withdraw.
POSTPONEMENT_CANCEL_QUERY_KEYWORDS = [
    "취소하고 싶", "취소하려", "취소해", "철회하고 싶", "철회하려",
    "그만두고 싶", "안 받고 싶", "포기하고 싶", "안 하고 싶",
    "자진", "조기", "빨리 가고", "일찍 가고",
]

USER_TYPE_KEYWORDS = {
    "영주권자": ["영주권", "그린카드"],
    "재외동포2세": ["재외국민 2세", "재외국민2세"],
    "이중국적자": ["복수국적", "이중국적"],
    # "유학" alone doesn't catch someone describing their program level
    # instead of the fact that they're studying abroad (e.g. "박사과정 중인데").
    "유학생": ["유학", "박사과정", "석사과정", "석박사", "학위과정", "대학원생"],
}

TOPIC_KEYWORDS = {
    "허가취소": ["허가취소", "허가 취소", "취소", "박탈", "자격 상실"],
    # "취업" already caught the formal phrasing; "아르바이트" is the far more
    # common way users describe casual/part-time work abroad.
    "영리활동": ["영리", "취업", "생업", "아르바이트"],
    "여비지급": ["여비", "항공료", "귀가", "귀향"],
    # "이민" is not just colloquial -- 국외여행 업무처리 규정 제8조 uses it as the
    # official category label for 국외이주 목적 국외여행허가, so it belongs here
    # on the corpus side too, not only as a query-side synonym.
    "국외여행허가": ["국외여행", "국외체재", "해외체재", "이민"],
    "휴가": ["휴가"],
    "복무": ["복무", "소집", "의무부과"],
    # Receiving a 국외여행허가/기간연장허가 IS the postponement mechanism (시행령
    # 제128조제1항이 이 연결고리) -- the statute almost never says "연기" outright
    # in those provisions, so without these the tag misses 149조/별표3/70조/
    # 146~147조 entirely even though they're the substance of "입영연기".
    # "언제까지"/"몇 살까지"/"나이 제한" ask about postponement duration without
    # ever saying "연기" itself (e.g. "영주권자인데 언제까지 입영 안 해도 되나요")
    # -- without these the question fell through to "일반", the directional
    # boost in routes/query.py never triggered, and 24조(자진 조기입영, tagged
    # 입영연기_취소) won purely on raw lexical/semantic overlap with "영주권자"/
    # "입영".
    "연기": [
        "연기", "미룰", "미뤄", "미루고", "늦출", "늦출 수",
        "국외여행허가", "국외여행기간 연장허가", "국외여행의 허가",
        "언제까지", "몇 살까지", "몇살까지", "나이 제한",
        # "늦게 가고 싶은데"/"천천히 입영해도"/"나중에 가도" 같은 표현은 "연기"라는
        # 법률 용어 없이 동사(가다/입영하다)에 부사(늦게/천천히/나중에)만 붙는 구조라
        # 위 명사형 키워드에 안 걸림. 방향은 전부 "자진 조기입영의 반대"이므로
        # 기본값인 _신청 방향으로 떨어짐 (POSTPONEMENT_CANCEL_QUERY_KEYWORDS의
        # "빨리 가고"/"일찍 가고"와 반대 극이라 서로 안 겹침).
        "늦게 가", "늦게 입영", "천천히 가", "천천히 입영",
        "나중에 가", "나중에 입영", "최대한 늦게",
    ],
    # "그냥 한국 안 들어가면 안 되나요" 같은 회피성 표현은 "위반"/"제재" 같은 법률
    # 용어를 전혀 안 쓰고 "안 들어가다"/"안 돌아오다"류 동사 부정문으로만 나타나서
    # 위 키워드에 안 걸렸다 (실측: topic_tags=['일반'], top1 관련도 0.0123).
    "제재": [
        "위반", "제재", "벌칙", "고발", "형사",
        "안 들어가", "안 들어오", "귀국 안 하", "귀국하지 않",
        "안 돌아가", "안 돌아오",
    ],
    "감면": ["감면", "면제"],
}

# Some user phrasing has essentially zero lexical/semantic overlap with the
# statute text that answers it, so BM25/dense retrieval can rank the right
# chunk far outside the candidate pool entirely (e.g. "자퇴" scored rank 168/270
# against 국외여행 업무처리 규정 제27조③, which never says "자퇴" -- it says
# "재학사실을...확인한 결과 허가요건을 유지하지 못한 경우"). A topic-tag boost
# on the reranked pool can't fix this if the chunk never enters the candidate
# pool in the first place, so these anchors force specific articles into the
# candidate set whenever their trigger words appear, regardless of BM25/dense
# rank. Keep this list to genuinely one-answer cases -- it's a targeted patch,
# not a general retrieval mechanism.
SYNONYM_ANCHOR_LOOKUPS = [
    {
        "keywords": ["휴학", "자퇴", "제적", "중퇴", "학교 그만"],
        "law_name": "병역의무자 국외여행 업무처리 규정",
        "article_no": "27",
    },
    # "안 들어가면"/"귀국 안 하면" 같은 회피 표현은 "기피"/"위반"이라는 법률 용어를
    # 안 쓰기 때문에 BM25/dense 둘 다 놓친다 (실측: top1이 관련 없는 별표3, 0.0123).
    # 정답은 제70조(허가의무 자체) + 제94조(그 의무 위반 시 처벌) 두 조문이다.
    {
        "keywords": [
            "안 들어가", "안 들어오", "귀국 안 하", "귀국하지 않",
            "안 돌아가", "안 돌아오",
        ],
        "law_name": "병역법",
        "article_no": "70",
    },
    {
        "keywords": [
            "안 들어가", "안 들어오", "귀국 안 하", "귀국하지 않",
            "안 돌아가", "안 돌아오",
        ],
        "law_name": "병역법",
        "article_no": "94",
    },
    {
        "keywords": ["아르바이트", "알바", "파트타임", "영리활동"],
        "law_name": "병역의무자 국외여행 업무처리 규정",
        "article_no": "22",
    },
]

# Deliberately out of the RAG dataset (see memory: project-katusa-scope-exclusion) --
# eligibility for these changes every year via MMA recruitment notices rather than
# statute, so answering from the law corpus would be misleading. Each category
# maps to the actual MMA recruitment-notice page for that program (not just a
# bare "go check mma.go.kr" shrug) -- "모집병" alone has no single specific page,
# so it's the catch-all with no url.
OUT_OF_SCOPE_CATEGORIES = {
    "카투사": {
        "keywords": ["카투사", "katusa"],
        "url": "https://www.mma.go.kr/contents.do?mc=mma0000525",
    },
    # Users don't always say the formal 훈령 term "어학병" -- "어학특기병"/
    # "어학병특기" are common variants, and "통역병" gets mentioned in the same
    # breath often enough (KATUSA interpreter-track discussions) to include.
    "어학병": {
        "keywords": ["어학병", "어학특기병", "어학병특기", "통역병"],
        "url": "https://www.mma.go.kr/contents.do?mc=mma0000522",
    },
    "모집병(기타)": {
        "keywords": ["모집병"],
        "url": None,
    },
}

OUT_OF_SCOPE_KEYWORDS = [
    kw for category in OUT_OF_SCOPE_CATEGORIES.values() for kw in category["keywords"]
]

OUT_OF_SCOPE_BASE_MESSAGE = (
    "카투사/어학병 등 모집병 구체적 지원자격(TOEIC 점수 등)은 매년 병무청 모집공고로 정해져서, "
    "이 챗봇의 법령 데이터베이스에는 포함되어 있지 않습니다."
)

# 카투사 and 어학병 aren't the same thing (카투사 is its own recruitment field;
# 어학병 is a language-specialty track run across several branches, KATUSA
# included) -- surfacing both links without this note invites the user to
# assume they're interchangeable or redundant.
OUT_OF_SCOPE_KATUSA_LANGUAGE_RELATION_NOTE = (
    "참고로 카투사와 어학병은 같은 게 아니에요 — 카투사는 별도 모집분야고, 어학병은 카투사를 "
    "포함한 여러 군에서 운영하는 특기병 분류라서, 카투사 내에서 어학병으로 지원하는 것도 "
    "가능합니다. 두 공고를 각각 확인해 보세요."
)

# When a scope-excluded question (카투사 등) also names a user type we DO cover,
# steer toward the adjacent thing we can actually answer: voluntary early
# enlistment while living overseas -- same underlying article the user type
# keyword table already knows about (병역의무자 국외여행 업무처리 규정 제24조,
# 영주권자 등 입영희망신청제도). routes/query.py uses this to fetch the actual
# chunks; this module only names which ones.
OUT_OF_SCOPE_RELATED_LOOKUP = {
    "law_name": "병역의무자 국외여행 업무처리 규정",
    "article_no": "24",
}

OUT_OF_SCOPE_GUIDANCE_WITH_USER_TYPE = (
    "다만 해외 거주 중인 {user_types}가 자진해서 조기 입영을 신청하는 절차는 안내해드릴 수 있어요 "
    "(영주권자 등 입영희망신청제도, 관련 조항을 아래에 같이 보여드릴게요)."
)

OUT_OF_SCOPE_GUIDANCE_GENERIC = (
    "혹시 해외 거주 중 자진 입영이나 입영 시기 조정에 대해 궁금하신 거라면, 그 부분은 답변해드릴 수 있어요."
)

# Project scope is "병역의무 발생 ~ 입영 전까지" (see docs/architecture.md) --
# questions about life AFTER service (전역, 제대) are out of scope the same way
# KATUSA is, but for a completely different reason (no data at all, not a
# yearly-changing notice), so they get their own category and message rather
# than being folded into OUT_OF_SCOPE_CATEGORIES's "check the MMA recruitment
# notice" framing, which would be actively misleading here.
POST_SERVICE_KEYWORDS = [
    "전역", "제대", "군복무 마친", "군복무를 마친", "전역 후", "제대하고", "전역하고",
    "갔다 온", "갔다온", "군대 다녀온", "복무를 마친", "복무 마친",
]

POST_SERVICE_FALLBACK_MESSAGE = (
    "이 챗봇은 '병역의무 발생 ~ 입영 전'까지의 절차만 다룹니다. 전역/제대 이후 사안은 "
    "관할 지방병무청으로 문의해 주세요."
)