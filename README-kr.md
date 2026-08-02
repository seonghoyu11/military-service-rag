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

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [아키텍처](#아키텍처)
- [기술 스택](#기술-스택)
- [데이터 출처](#데이터-출처)
- [프로젝트 구조](#프로젝트-구조)
- [시작하기](#시작하기)
  - [사전 준비](#사전-준비)
  - [1. 환경변수 설정](#1-환경변수-설정)
  - [2. 의존성 설치](#2-의존성-설치)
  - [3. 법령 코퍼스를 MongoDB에 적재 (최초 1회)](#3-법령-코퍼스를-mongodb에-적재-최초-1회)
  - [4. 백엔드 실행](#4-백엔드-실행)
  - [5. UI 열기](#5-ui-열기)
- [평가 결과](#평가-결과)
- [개발자 노트](#개발자-노트)
- [License](#license)

## 프로젝트 개요

병역법 체계는 조항 간 참조가 복잡하고, 해외체류자(영주권자/유학생/이중국적자/
재외동포 2세)마다 적용되는 예외 조항이 다릅니다. 이 프로젝트는 단순 LLM
프롬프팅이 아니라, 아래와 같은 구조화된 파이프라인으로 정확도를 높이는 것을
목표로 합니다.

- 법조문의 조/항/호 구조를 유지한 파싱 및 청킹
- Intent Classifier로 유저 유형·질문 목적 1차 분류
- BM25 + Dense Embedding 하이브리드 검색
- Reranker로 최종 근거조항 정렬
- Google Gemini API로 근거조항 citation 포함 답변 생성
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
                  [Google Gemini API (Gemini 3.5 Flash)]
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
| LLM | Google Gemini API (Gemini 3.5 Flash) |
| 프론트 | Next.js, next-intl (영/한 토글) |
| 평가 | RAGAS |

---

## 데이터 출처

[법제처 국가법령정보센터](https://www.law.go.kr)에서 수집한 공공저작물입니다.

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
├── generation/          # Gemini API 답변 생성 연동
├── routes/             # Flask API 엔드포인트
├── db/                 # MongoDB 연결
└── evaluation/         # RAGAS 기반 정량 평가

frontend/               # prototype.html(현재 동작하는 UI) + Next.js 앱 스캐폴딩(7단계, 미구현)
scripts/                # DB 세팅 및 파이프라인 실행 스크립트
docs/                   # 아키텍처 설명, 평가 결과 정리
```

## 시작하기

### 사전 준비
- Python 3.12+
- [MongoDB Atlas](https://www.mongodb.com/atlas) 클러스터 (무료 M0 티어로 충분 —
  Atlas Vector Search도 무료 티어에서 사용 가능) + 연결 문자열
- [Google AI Studio](https://aistudio.google.com/apikey) API 키 (무료 티어,
  카드 등록 불필요)

### 1. 환경변수 설정
```bash
cd backend
cp .env.example .env   # GOOGLE_API_KEY, MONGO_URI 입력
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt --break-system-packages
```

### 3. 법령 코퍼스를 MongoDB에 적재 (최초 1회)
파싱된 법령 청크 272개를 임베딩하고, 하이브리드 검색이 실제로 사용하는 Atlas
Vector Search 인덱스까지 생성합니다:
```bash
python pipeline/load_to_mongo.py
```
Atlas에서 인덱스가 빌드되는 데 1~2분 걸릴 수 있고, 스크립트가 쿼리 가능
상태가 될 때까지 알아서 대기합니다.

### 4. 백엔드 실행
```bash
python app.py
```
API는 http://localhost:5001 에서 서비스됩니다. 첫 요청은 임베딩/리랭커
모델이 그때 처음 로드되기 때문에 느립니다.

### 5. UI 열기
Next.js 프론트엔드(7단계)는 아직 구현 전입니다 — 지금 실제로 동작하는
화면은 위 API에 직접 요청을 보내는 정적 HTML/JS 페이지
[`frontend/prototype.html`](frontend/prototype.html) 하나뿐입니다:
```bash
open frontend/prototype.html   # 또는 Finder에서 더블클릭
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
