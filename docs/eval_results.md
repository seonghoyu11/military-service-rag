# 평가 결과

## 2단계: 임베딩 모델 비교 (2026-07-09)

### 방법
- `backend/data/eval/test_queries.json`: 실제 케이스 기반 시나리오 + 병무청 FAQ 스타일 질문 15개
  (질문 → 정답 조항 `law_name`/`article_no`/`paragraph_no` 라벨링), 그 중 1개(id=15, 카투사)는
  의도적 스코프 밖 네거티브 테스트
- 후보 3개 모델로 272개 청크 + 15개 질문 임베딩 후 cosine similarity로 Recall@5, Recall@10, MRR 계산
  (`backend/evaluation/compare_embeddings.py`)

### 결과

| 모델 | Recall@5 | Recall@10 | MRR | 긍정 평균 top1 | 부정(카투사) top1 |
|---|---|---|---|---|---|
| **BGE-m3** | 0.929 (13/14) | **1.0 (14/14)** | 0.746 | 0.723 | 0.443 |
| multilingual-e5-large | 0.929 (13/14) | 0.929 (13/14) | **0.816** | 0.887 | 0.801 |
| KoE5 | 0.857 (12/14) | 0.929 (13/14) | 0.612 | 0.694 | 0.264 |

### 선정: BGE-m3

- Recall@10 만점(14/14)이고, 긍정/부정 질문 간 유사도 점수 구분이 가장 뚜렷함
  (multilingual-e5-large는 스코프 밖 질문에도 top1 유사도 0.801을 줘서 절대 점수만으로
  "관련 조항 없음"을 판단하기 어려움)
- 부가 이점: BGE-m3는 dense + sparse(lexical weight) 임베딩을 한 모델에서 함께 뽑을 수 있어,
  3단계 BM25+Dense 하이브리드 검색 구현 시 참고 가능
- KoE5(한국어 특화 모델)가 오히려 가장 낮은 성능 — 이 규모(560M) 모델 간 우열은
  "한국어 특화 여부"보다 retrieval contrastive 학습 방식/데이터 품질 차이가 더 크게 작용하는 것으로 보임

### 시사점: 하이브리드 검색(3단계)의 필요성 실증

- 질문 14번("국외여행허가 없이 계속 출국을 미루면 어떤 불이익이 있나요?")의 정답 조항
  (병역법 제70조 제2항)은 본문에 "기피"라는 단어가 그대로 들어있는데도, **3개 모델 전부 top-5를
  놓침** (순위 9~19위). Dense 임베딩만으로는 이런 어휘 일치 케이스를 놓칠 수 있어,
  BM25(어휘 매칭)를 병행하는 하이브리드 설계가 실제로 필요하다는 근거가 됨.

### 인프라
- MongoDB Atlas Vector Search 인덱스(`law_chunks_vector_index`, cosine, 1024차원)에 272개 청크
  전체를 BGE-m3로 임베딩하여 적재 완료. `$vectorSearch` 실제 쿼리로 검증함
  (`backend/pipeline/load_to_mongo.py`).
