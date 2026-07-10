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

### 3단계 이후: 미착수
Hybrid Retrieval(BM25+Dense+Reranker), Intent Classifier, Claude API 연동, Flask API, Next.js
프론트 — 계획대로 순서대로 진행 예정.

## 스코프 결정 사항
- **카투사/어학병 등 모집병**: 데이터셋에 포함하지 않기로 결정 (지원자격이 법조문이 아니라 매년
  바뀌는 병무청 모집공고 성격이라 RAG에 넣어도 금방 outdated되고, 관련 훈령을 제대로 넣으려면
  준용조항이 끝없이 딸려와 스코프가 무한정 커짐). 관련 질문은 Intent Classifier 단계에서 키워드
  매칭으로 감지해 "구체적 지원자격은 매년 병무청 모집공고에서 확인 필요" fallback 안내로 응답할
  예정 (아직 미구현).
