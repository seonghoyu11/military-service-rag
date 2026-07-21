# 해외체류 병역의무자 안내 챗봇 (Military Service RAG Chatbot)

> **For English Speakers**:
> Please refer to [README.md](README.md) for English Information

영주권자, 유학생, 이중국적자, 재외동포 2세 등 해외체류 병역의무자를 위한
RAG 기반 병역 행정절차 안내 챗봇입니다.

> ⚠️ **⚠️ 주의 사항 및 면책 조항**
> 이 프로젝트는 개인 학습 및 포트폴리오 목적으로 제작되었으며, 병무청의 공식
> 서비스가 아닙니다. 본 챗봇이 제공하는 답변은 법률 자문이 아닌 정보 제공
> 목적이며, 실제 병역 관련 의사결정은 반드시 병무청(국번없이 1588-9090) 또는
> 관할 지방병무청, 재외공관을 통해 확인하시기 바랍니다.

---

## 프로젝트 개요

병역법 체계는 조항 간 참조가 복잡하고, 해외체류자(영주권자/유학생/이중국적자/
재외동포 2세)마다 적용되는 예외 조항이 다릅니다. 이 프로젝트는 단순 LLM
프롬프팅이 아니라, 아래와 같은 구조화된 파이프라인으로 정확도를 높이는 것을
목표로 합니다.

- 법조문의 조/항/호 구조를 유지한 파싱 및 청킹
- Intent Classifier로 유저 유형·질문 목적 1차 분류
- BM25 + Dense Embedding 하이브리드 검색
- Reranker로 최종 근거조항 정렬
- Claude API로 근거조항 citation 포함 답변 생성
- RAGAS 기반 정량 평가

**스코프**: 병역의무 발생 ~ 입영 전까지의 행정절차 (본인 미입영 상태 반영)

---

## 아키텍처

```
[Next.js 프론트] ←→ [Flask 백엔드] ←→ [MongoDB Atlas]
                          │              (유저/대화/피드백 + 벡터DB 겸용)
                          ↓
                  [Intent Classifier]
                          ↓
              [Hybrid Retrieval: BM25 + Dense + Reranker]
                          ↓
                  [Claude API (Haiku 4.5)]
```

자세한 설명은 [`docs/architecture.md`](docs/architecture.md) 참고.

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| 백엔드 | Flask, Flask-CORS |
| DB / 벡터DB | MongoDB Atlas (Vector Search) |
| 임베딩 | sentence-transformers (BGE-m3) |
| 검색 | rank_bm25 (BM25) + Dense Hybrid |
| Reranker | bge-reranker-v2-m3 |
| 분류기 | KoBERT/KoELECTRA + linear head |
| LLM | Anthropic API (Claude Haiku 4.5) |
| 프론트 | Next.js, next-intl (영/한 토글) |
| 평가 | RAGAS |

---

## 데이터 출처

[법제처 국가법령정보센터](law.go.kr)에서 수집한 공공저작물입니다.

- [병역법](https://www.law.go.kr/법령/병역법)
- [병역법 시행령](https://www.law.go.kr/법령/병역법시행령)
- [병역법 시행규칙](https://www.law.go.kr/법령/병역법시행규칙)
- [병역의무자 국외여행 업무처리 규정 (병무청훈령)](https://www.law.go.kr/행정규칙/병역의무자국외여행업무처리규정/(2141,20250502))
- [국외영주권자 등 병 복무시 휴가여비 및 전역시 귀가여비 지급 훈령 (국방부훈령)](https://www.law.go.kr/행정규칙/국외영주권자등병복무시휴가여비및전역시귀가여비지급훈령/(2414,20200413))
- [[별표 3] 국외이주 목적의 국외여행허가 또는 기간연장허가](https://www.law.go.kr/LSW/admRulBylInfoPLinkR.do?bylBrNo=00&admRulNm=%EB%B3%91%EC%97%AD%EC%9D%98%EB%AC%B4%EC%9E%90+%EA%B5%AD%EC%99%B8%EC%97%AC%ED%96%89+%EC%97%85%EB%AC%B4%EC%B2%98%EB%A6%AC+%EA%B7%9C%EC%A0%95&joEfYd=&bylCls=BE&bylClsCd=BE&bylEfYd=&bylNo=0003&admRulSeq=0)

## 프로젝트 구조

```
backend/
├── data/               # 원본 PDF, 파싱된 JSON, 평가용 test set
├── pipeline/           # 파싱 → 청킹 → 태깅 → 임베딩
├── retrieval/          # BM25 / Dense / Hybrid / Reranker
├── classifier/         # Intent classifier 학습·추론
├── llm/                # Claude API 연동
├── routes/             # Flask API 엔드포인트
├── db/                 # MongoDB 연결
└── evaluation/         # RAGAS 기반 정량 평가

frontend/               # Next.js 앱 (챗 UI, 프로필, 영한 토글)
scripts/                # DB 세팅 및 파이프라인 실행 스크립트
docs/                   # 아키텍처 설명, 평가 결과 정리
```

## 시작하기

```bash
# 백엔드
cd backend
pip install -r requirements.txt --break-system-packages
cp .env.example .env   # ANTHROPIC_API_KEY, MONGO_URI 입력
python app.py

# 프론트엔드
cd frontend
npm install
npm run dev
```

## 평가 결과

정량 평가(retrieval 정확도, answer faithfulness 등) 결과는
[`docs/eval_results.md`](docs/eval_results.md)에 정리되어 있습니다.

## 개발자 노트

개발자 노트가 [`docs/devlog.md`](docs/devlog.md)에 상세히 기록되어 있습니다.

---

## License

법령 원문은 공공저작물로 저작권 제한이 없습니다. 코드는 개인 포트폴리오
목적으로 작성되었습니다.
