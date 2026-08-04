# Backend — DutyCompass Flask API

> English version: [README-en.md](README-en.md)

병역법·시행령·시행규칙·병무청/국방부 훈령·별표3을 파싱한 법령 청크를 BM25+Dense
하이브리드 검색 → 리랭커 → (신뢰도 높으면) Gemini 답변 생성 순으로 처리하는
Flask API 서버. 전체 아키텍처는 [`docs/architecture.md`](../docs/architecture.md),
단계별 개발 기록은 [`docs/devlog.md`](../docs/devlog.md), 정량/정성 평가 전체
로그는 [`docs/eval_results.md`](../docs/eval_results.md) 참고.

## 디렉토리 구조

```
backend/
├── app.py                  # Flask 앱 팩토리, blueprint 등록, 기동 로그
├── config.py                # .env 로드 (GOOGLE_API_KEY, MONGO_URI, MONGO_DB_NAME)
├── requirements.txt
├── classifier/              # 규칙 기반 의도/유저타입 분류
├── pipeline/                 # PDF 파싱 → 청킹 → 태깅 → 임베딩 → Mongo 적재
├── retrieval/                 # BM25 / Dense / Hybrid / Reranker
├── generation/                # Gemini 답변 생성 + citation 파싱
├── routes/                    # Flask 엔드포인트 (query / profile / feedback)
├── db/                         # MongoDB 연결
├── evaluation/                  # 임베딩·하이브리드 alpha 튜닝 + RAGAS 정량 평가
├── tests/                       # pytest 유닛테스트
└── data/                        # 원본 PDF / 파싱 결과 / 평가셋
```

## classifier/ — 규칙 기반 분류기

이름과 달리 학습된 ML 모델이 아니라 **키워드 테이블 기반 규칙 분류기**다
(`train.py`는 향후 학습형 분류기를 위한 빈 스텁). `model.py`가 정의하는
테이블을 질문 쪽(`predict.py`)과 코퍼스 쪽(`pipeline/tagger.py`)이 공유해서
같은 태그 어휘를 쓴다.

- **`model.py`**
  - `USER_TYPE_KEYWORDS`: 유저타입 4종(영주권자/재외동포2세/이중국적자/유학생) → 키워드 목록
  - `TOPIC_KEYWORDS`: 토픽 8종(허가취소/영리활동/여비지급/국외여행허가/휴가/복무/연기/제재/감면) → 키워드 목록
  - `POSTPONEMENT_CANCEL_PATTERN` / `POSTPONEMENT_CANCEL_QUERY_KEYWORDS`: "연기" 토픽을
    입영연기_신청/입영연기_취소로 방향성 분기하는 정규식·키워드
  - `SYNONYM_ANCHOR_LOOKUPS`: 트리거 키워드가 있으면 특정 조항을 검색 후보 풀에
    강제 포함시키는 `{keywords, law_name, article_no}` 목록 (예: 휴학/자퇴 →
    국외여행 업무처리 규정 제27조, 아르바이트/알바 → 제22조) — 법조문과 어휘
    중첩이 거의 없는 질문 표현을 구제하기 위한 장치
  - `OUT_OF_SCOPE_CATEGORIES`/`OUT_OF_SCOPE_KEYWORDS` 등: 카투사/어학병/모집병처럼
    이 프로젝트 스코프 밖인 질문을 감지하고 안내 메시지·관련 조항을 반환하는 테이블
  - `POST_SERVICE_KEYWORDS`: 전역/제대 등 "병역의무 이행 이후" 질문(스코프 밖,
    데이터 자체가 없음) 감지용
- **`predict.py`**: `classify(question, session_user_type=None)` — 위 테이블들을
  적용해 `{user_type_tags, topic_tags, out_of_scope, fallback_message,
  related_lookup, anchor_lookups}`를 반환. 판정 순서: 전역/제대 질문 → OOS
  카테고리 → (정상 범위면) 유저타입/토픽 태깅 + anchor_lookups 계산.

## pipeline/ — 원본 PDF → 청크 → Mongo

- **`parser.py`**: `pdfplumber`로 5개 표준 법령 PDF를 파싱(`parse_standard_law`,
  머리말/꼬리말 제거, 줄바꿈 복구, 개정이력 태그 제거 후 `제N조(...)` /
  원문자(①-⑳) 기준으로 조·항 분리). `parse_별표3`는 표 형태 PDF 전용 파서
  (병합 셀 forward-fill 후 자연어 문장으로 변환).
- **`chunker.py`**: `chunk_articles`가 조 단위(500자 이하 또는 항 1개)면 조
  단위로, 아니면 항 단위로 청크 분할하고 `[법명 제N조(제목)]` 헤더를 붙임.
  `extract_references`로 본문 인용 조항(`refers_to`)도 추출.
- **`tagger.py`**: `classifier/model.py`의 키워드 테이블로 각 청크에
  `user_type_tags`/`topic_tags`를 부여(`tag_chunk`/`tag_chunks`). 국외여행
  업무처리 규정 제24조는 예외적으로 연기/입영연기_취소를 강제 부여.
- **`embedder.py`**: 임베딩 모델 3종(`bge-m3`/`multilingual-e5-large`/`koe5`) 설정과
  `embed_passages`/`embed_queries` 래퍼. 실제 운영에는 `bge-m3` 사용.
- **`load_to_mongo.py`**: `data/processed/law_chunks.json`을 읽어 `bge-m3`로
  임베딩하고 MongoDB `law_chunks` 컬렉션에 적재, Atlas Vector Search 인덱스
  (`law_chunks_vector_index`, 1024차원 코사인 + user_type_tags/topic_tags
  필터 필드)를 생성/재생성하고 queryable 상태까지 폴링.
- **`run_pipeline.py`**: PDF 파싱→청킹→태깅 전체를 실행해 `law_chunks.json`을
  생성하는 엔드투엔드 스크립트(경로가 절대경로로 하드코딩돼 있음, 주의).

## retrieval/ — 하이브리드 검색 + 리랭커

- **`bm25_search.py`**: `kiwipiepy.Kiwi`로 한국어 형태소 분석 후 조사/어미를
  제외한 내용어 품사만 남겨 `rank_bm25.BM25Okapi` 인덱스 구성.
- **`vector_search.py`**: MongoDB Atlas `$vectorSearch`로 직접 쿼리(질문을
  `bge-m3`로 임베딩 후 검색).
- **`hybrid.py`**: BM25/Dense 점수를 min-max 정규화 후 `alpha` 가중합
  (`DEFAULT_ALPHA=0.3`, `evaluation/tune_hybrid.py` 그리드서치로 튜닝된 값).
- **`reranker.py`**: `BAAI/bge-reranker-v2-m3` cross-encoder로 후보를
  재정렬(CPU 강제 — MPS 메모리 압박 회피). `rerank(query, candidates, top_k=5)`.

## generation/ — Gemini 답변 생성

- **`gemini_client.py`**: 무료 티어 모델 화이트리스트(`ALLOWED_MODELS`)와
  429 백오프가 있는 `generate()` 래퍼. `DEFAULT_MODEL`은 실측 RPD(일일 요청
  한도) 문제로 여러 번 바뀐 이력이 있음 — 현재값과 사유는 파일 상단 주석과
  `docs/eval_results.md`의 "Stage 5"/"Stage 5 기본 모델 lite 전환" 섹션 참고.
- **`answer.py`**: `generate_answer(question, results)` — 검색 결과만 근거로
  답변하도록 강제하는 시스템 프롬프트. 별표(표) 출처는 "제N조" 대신
  "별표 N" 표기하도록 별도 분기.
- **`citation_parser.py`**: `parse_citations(answer_text, results)` — 평문
  답변을 프론트 citation 칩용 `{type:"text"|"citation", ...}` 세그먼트로
  분해. `results`에 이미 있는 정확한 `law_name` 문자열로 정규식을 동적
  구성하는 방식(법령명에 공백이 낀 경우까지 커버, 별표 케이스도 별도 패턴
  없이 통합 처리). 별표 4중 인용처럼 후보가 여럿이면 순서 기반 폴백을
  쓰는 known limitation이 있음 — 자세한 사유는 파일 내 독스트링 참고.
- **`ragas_llm.py`**: RAGAS의 LLM judge가 `gemini_client.generate()`를
  경유하도록 감싼 `WhitelistedGeminiChatModel` (judge 호출도 동일한 화이트리스트/
  백오프를 통과하게 하려는 목적).

## routes/ — Flask 엔드포인트

| 파일 | 메서드/경로 | 설명 |
|---|---|---|
| `query.py` | `POST /api/query` | `answer_question()` 순수 함수로 분리됨(RAGAS가 HTTP 없이 직접 호출) — 분류→검색→리랭크→(신뢰도 높으면)생성까지 전체 파이프라인 |
| `profile.py` | `POST /api/profile` | 세션 프로필(로그인 없음) upsert — `session_id` 기준, `VALID_USER_TYPES` 5종 검증 |
| `profile.py` | `GET /api/profile/<session_id>` | 세션 프로필 조회 |
| `feedback.py` | `POST /api/feedback` | 👍/👎 + 코멘트 + 당시 결과 스냅샷 저장(외래키 아님, `/api/query`가 stateless라서 통째로 저장) |

## db/

**`mongo.py`**: 모듈 import 시 `MongoClient(config.MONGO_URI)` 1개를 생성,
`get_db()`가 `config.MONGO_DB_NAME` DB를 반환. 이 프로젝트가 쓰는 컬렉션:
`law_chunks`(pipeline/retrieval), `profiles`(routes/profile.py),
`feedback`(routes/feedback.py).

## evaluation/

- **`compare_embeddings.py`**: 임베딩 모델 3종 비교 스크립트 →
  `data/eval/embedding_comparison_results.json` 생성.
- **`tune_hybrid.py`**: `hybrid.py`의 `alpha` 그리드서치 →
  `data/eval/hybrid_alpha_grid_results.json` 생성 (alpha=0.3에서 MRR 최고).
- **`ragas_eval.py`**: RAGAS 정량 평가(faithfulness/answer_relevancy/
  context_precision/context_recall) 정식 실행 스크립트. 실행 결과/이슈
  히스토리는 `docs/eval_results.md`에 상세 기록돼 있음.
- **`ragas_embeddings.py`**: RAGAS answer_relevancy용 로컬 BGE-m3 임베딩
  래퍼(`pipeline/embedder.py` 재사용, 네트워크 호출 없음).
- **`results/`**: 현재 비어있음.
- `run_eval.py`: 빈 스텁(미구현).

## tests/

`test_citation_parser.py` — `generation/citation_parser.py`의 유닛테스트.
`fixtures/citation_case1.json`/`citation_case2.json`은 실제 `/api/query`
응답을 그대로 캡처한 것(손으로 작성 안 함) — 별표 4중 인용, 공백 낀
법령명 매칭 두 케이스를 내용까지 검증. `cd backend && python3 -m pytest
tests/`로 실행.

## data/

- `raw/`: 원본 PDF 6개(병역법/시행령/시행규칙/국외여행 업무처리 규정/
  국외영주권자 여비지급 훈령/별표3).
- `processed/law_chunks.json`: 파싱·청킹·태깅 완료된 최종 청크 270개.
- `eval/test_queries.json`: 검색 품질 평가용 15문항(정답 조항 라벨 포함).
- `eval/ragas_eval_set.json`: RAGAS 평가용 8문항(일부 ground_truth 포함).
- `eval/embedding_comparison_results.json`, `eval/hybrid_alpha_grid_results.json`:
  위 evaluation/ 스크립트들의 산출물.

## 실행

전체 셋업(.env, MongoDB, 의존성 설치)은 최상위 [`README.md`](../README.md)
"Getting Started" 참고. 요약:

```bash
cd backend
cp .env.example .env   # GOOGLE_API_KEY, MONGO_URI 채우기
pip install -r requirements.txt --break-system-packages
python pipeline/load_to_mongo.py   # 최초 1회
python app.py                       # http://localhost:5001
```
