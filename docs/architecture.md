# 아키텍처 및 진행 상황

## 전체 구조
```
[Next.js 프론트] <-> [Flask 백엔드] <-> [MongoDB Atlas]
                          |        (유저/대화/피드백 + 벡터DB 겸용)
                          v
                  [Intent Classifier]
                          v
              [Hybrid Retrieval: BM25 + Dense + Reranker]
                          v
                  [Claude API (Haiku 4.5)] -> 근거조항 citation 포함 답변
```

## 스코프
병역의무 발생 ~ 입영 전까지의 행정절차 안내. 입영 이후(부대배치, 카투사/어학병 등 모집병
지원자격 등)는 스코프 밖으로 명시적으로 제외함 — 상세 사유는 `docs/eval_results.md`의
테스트셋 id=15 항목 및 이하 결정 사항 참고.

## 데이터 원본 (6개, 축약본)
병역법, 병역법 시행령, 병역법 시행규칙, 병역의무자 국외여행 업무처리 규정(병무청훈령),
국외영주권자 등 병 복무시 휴가여비 지급 훈령(국방부훈령), 별표3(국외이주 허가기준표)

## 진행 상황

### 1단계: 데이터 파싱 파이프라인 — 완료
- `pipeline/parser.py`, `chunker.py`, `tagger.py` → `data/processed/law_chunks.json` (272개 청크)
- 조/항 구조 유지, 별표3은 행 단위 자연어 문장 변환, user_type_tags/topic_tags/refers_to 메타데이터
- 검증 과정에서 발견해 수정한 이슈:
  - `refers_to`가 청크 헤더의 자기 조번호를 참조로 오인식하던 버그 (270개 중 224개 오염 → 수정 후 2개만
    남고 그 2개도 실제 본문 자기참조로 확인됨)
  - PDF 줄바꿈이 단어 중간에서 끊긴 채 저장되던 문제 (582건 → 22건, 남은 건 대부분 정상적인
    가/나/다 목록 마커)
  - 별표3 카테고리 라벨이 PDF 테이블 셀 추출 시 공백이 끼어 깨지던 문제 수정

### 2단계: 임베딩 모델 비교 + MongoDB 적재 — 완료
- BGE-m3 / multilingual-e5-large / KoE5 3개 후보를 자체 제작 테스트셋(`data/eval/test_queries.json`,
  15문항)으로 Recall@K, MRR 비교 → **BGE-m3 선정** (상세 결과는 `docs/eval_results.md`)
- BGE-m3로 272개 청크 임베딩 후 MongoDB Atlas Vector Search 인덱스(`law_chunks_vector_index`)에 적재,
  `$vectorSearch` 쿼리로 동작 검증 완료
- 인프라: `config.py`(.env 로드), `db/mongo.py`(공유 커넥션 헬퍼)

### 3단계: Hybrid Retrieval (BM25 + Dense + Reranker) — 완료
- `retrieval/bm25_search.py`: kiwipiepy로 형태소 분석 후 조사/어미를 제거한 content word만으로
  BM25 인덱싱 (단독으로도 테스트셋 Recall@5 = 1.0)
- `retrieval/vector_search.py`: Atlas `$vectorSearch` 래퍼
- `retrieval/hybrid.py`: BM25 + Dense 점수를 min-max 정규화 후 가중합. 그리드서치로
  `alpha=0.3`(BM25 70% + Dense 30%) 확정 → Recall@5/10 만점, MRR 0.929
- `retrieval/reranker.py`: BAAI/bge-reranker-v2-m3 cross-encoder로 재정렬. Recall/MRR 자체는
  큰 이득이 없었지만, 스코프 밖 질문에 0.000점을 주는 등 점수 해석 가능성이 훨씬 좋아서
  "관련 조항 없음" 판단용 신뢰도 점수로 채택
- 이 검증 과정에서 테스트셋 자체의 라벨 오류(14번 문항 정답 누락)도 하나 발견해 수정함

### 4단계: Intent Classifier (경량, rule-based) — 완료
- `classifier/model.py`: 유저타입(영주권자/유학생/이중국적자/재외동포2세) × 주제(연기/국외여행허가/
  허가취소/영리활동/여비지급/복무/제재/감면/휴가) 키워드 테이블 + 스코프 밖(카투사 등) 키워드
- `classifier/predict.py`: 질문 텍스트에 규칙 적용, 스코프 밖 키워드 매칭 시 법조항 검색 대신
  fallback 안내 문구 반환
- `pipeline/tagger.py`가 같은 키워드 테이블을 `classifier/model.py`에서 가져다 쓰도록 리팩터링해서
  청크 태깅과 질문 분류가 같은 태그 체계를 유지하도록 함 (나중에 태그 필터링 검색에 활용 가능)
- 테스트셋 15문항으로 검증: 대부분 정확히 분류되고, 구어체 표현("미룰 수 있나요" 등)은 동의어
  키워드를 보강해서 대응. 암묵적 문맥(예: 이전 질문에서 언급된 영주권자라는 정보가 후속 질문에는
  없는 경우)은 규칙 기반 분류기의 한계로 남겨둠 — 계획대로 데이터가 쌓이면 경량 분류기로 교체 예정

### 5단계 이후: 미착수
Claude API 연동, Flask API, Next.js 프론트 — 계획대로 순서대로 진행 예정.

## 스코프 결정 사항
- **카투사/어학병 등 모집병**: 데이터셋에 포함하지 않기로 결정 (지원자격이 법조문이 아니라 매년
  바뀌는 병무청 모집공고 성격이라 RAG에 넣어도 금방 outdated되고, 관련 훈령을 제대로 넣으려면
  준용조항이 끝없이 딸려와 스코프가 무한정 커짐). 관련 질문은 Intent Classifier에서 키워드
  매칭으로 감지해 "구체적 지원자격은 매년 병무청 모집공고에서 확인 필요" fallback 안내로 응답
  (4단계에서 구현 완료).
- **프론트엔드 한/영 토글**: 7단계에서 next-intl로 구현 예정 (재외국민 타겟이라 필수).
