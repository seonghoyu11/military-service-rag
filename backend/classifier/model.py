# Rule-based keyword tables shared by the intent classifier (query-side) and
# the chunk tagger (corpus-side), so both stay in sync on what each tag means.
# Swap in a lightweight trained classifier here once enough labeled query data
# has accumulated (see project plan, stage 4).

USER_TYPE_KEYWORDS = {
    "영주권자": ["영주권"],
    "재외동포2세": ["재외국민 2세", "재외국민2세"],
    "이중국적자": ["복수국적"],
    "유학생": ["유학"],
}

TOPIC_KEYWORDS = {
    "허가취소": ["허가취소", "허가 취소", "취소"],
    "영리활동": ["영리", "취업", "생업"],
    "여비지급": ["여비", "항공료", "귀가", "귀향"],
    "국외여행허가": ["국외여행", "국외체재", "해외체재"],
    "휴가": ["휴가"],
    "복무": ["복무", "소집", "의무부과"],
    "연기": ["연기", "미룰", "미뤄", "미루고", "늦출", "늦출 수"],
    "제재": ["위반", "제재", "벌칙", "고발", "형사"],
    "감면": ["감면", "면제"],
}

# Deliberately out of the RAG dataset (see memory: project-katusa-scope-exclusion) --
# eligibility for these changes every year via MMA recruitment notices rather than
# statute, so answering from the law corpus would be misleading.
OUT_OF_SCOPE_KEYWORDS = ["카투사", "katusa", "어학병", "모집병"]

OUT_OF_SCOPE_FALLBACK_MESSAGE = (
    "카투사/어학병 등 모집병 지원 자격은 법조문이 아니라 매년 바뀌는 병무청 모집공고로 "
    "정해집니다. 최신 지원 자격은 병무청 홈페이지의 모집공고를 확인해 주세요."
)