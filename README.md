# DutyCompass - Military Service RAG Chatbot for Overseas Conscripts

> **한국인들을 위한 알림**:
> 한국어로 된 README는 [README-kr.md](README-kr.md)를 참고하십시오.

An LLM (RAG)-based chatbot designed to provide administrative guidance on military service for overseas Korean conscripts, including permanent residents, international students, dual citizens, and second-generation overseas South Koreans.

> **⚠️⚠️ Disclaimer**
> This project was developed solely for personal learning and portfolio purposes and is NOT an official service of the Military Manpower Administration (MMA). 
> The responses provided by this chatbot are for informational purposes only, not legal advice. 
> For official decisions regarding military service, please consult the MMA (+82-1588-9090), regional MMA offices, or your local Korean Embassy/Consulate.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
  - [Tech Stack](#tech-stack)
- [Data Sources](#data-sources)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Configure environment](#1-configure-environment)
  - [2. Install dependencies](#2-install-dependencies)
  - [3. Load the law corpus into MongoDB (one-time)](#3-load-the-law-corpus-into-mongodb-one-time)
  - [4. Start the backend](#4-start-the-backend)
  - [5. Open the UI](#5-open-the-ui)
- [API Reference](#api-reference)
- [Evaluation Results](#evaluation-results)
- [Development Logs](#development-logs)
- [License](#license)

## Project Overview
The South Korean Military Service Act features highly complex cross-references between clauses, and exception clauses vary significantly based on the user's status (e.g., permanent resident, international student, dual citizen, or second-generation overseas Korean). Rather than relying on simple LLM prompting, this project implements a highly structured pipeline to maximize retrieval accuracy:

- Structured Parsing & Chunking: Preserves the hierarchical document structure (Article/Paragraph/Item) of legal texts.
- Intent Classifier: Classifies user types and question intent upfront as a primary filter.
- BM25 + Dense Embedding Hybrid Search
- Reranker: Sorts and optimizes the final retrieved source articles.
- Google Gemini API: Generates responses that include precise citations of the supporting articles.
- RAGAS-based Quantitative Evaluation

**Scope**: Administrative procedures from the inception of military service obligation up to the point prior to enlistment (reflecting the user's current non-enlisted status).

---

## Architecture

```
[Next.js Frontend] ←→ [Flask Backend] ←→ [MongoDB Atlas]
                             │               (User/Chat/Feedback + Hybrid Vector DB)
                             ↓
                     [Intent Classifier]
                             ↓
             [Hybrid Retrieval: BM25 + Dense + Reranker]
                             ↓
                     [Google Gemini API (Gemini 3.5 Flash)]
```

For a detailed walkthrough, please refer to [`docs/architecture-en.md`](docs/architecture-en.md).

---

### Tech Stack

| Layer | 기술 |
|---|---|
| Backend | Flask, Flask-CORS |
| DB / Vector DB | MongoDB Atlas (Vector Search) |
| Embeddings | sentence-transformers (BGE-m3) |
| Retrieval | rank_bm25 (BM25) + Dense Hybrid |
| Reranker | bge-reranker-v2-m3 |
| Classifier | KoBERT/KoELECTRA + linear head |
| LLM | Google Gemini API (Gemini 3.5 Flash) |
| Frontend | Next.js, next-intl (영/한 토글) |
| Evaluation | RAGAS |

---

## Data Sources

The following documents are public government works collected from the [National Legal Information Center](https://www.law.go.kr) of the Republic of Korea. Documents are written in Korean, and English-translated documents (if available) can be accessed at this [link](https://www.law.go.kr/engLsSc.do?menuId=1&subMenuId=21&tabMenuId=117).

- [Military Service Act](https://www.law.go.kr/법령/병역법)
- [Enforcement Decree of the Military Service Act](https://www.law.go.kr/법령/병역법시행령)
- [Enforcement Rule of the Military Service Act](https://www.law.go.kr/법령/병역법시행규칙)
- [Regulations on Overseas Travel of Military Conscripts (MMA Directive)](https://www.law.go.kr/행정규칙/병역의무자국외여행업무처리규정/(2141,20250502))
- [Directive on Leave and Return Expenses for Enlisted Permanent Residents (MND Directive)](https://www.law.go.kr/행정규칙/국외영주권자등병복무시휴가여비및전역시귀가여비지급훈령/(2414,20200413))
- [[Table 3] Overseas Travel Permission or Extension for Emigration Purposes](https://www.law.go.kr/LSW/admRulBylInfoPLinkR.do?bylBrNo=00&admRulNm=%EB%B3%91%EC%97%AD%EC%9D%98%EB%AC%B4%EC%9E%90+%EA%B5%AD%EC%99%B8%EC%97%AC%ED%96%89+%EC%97%85%EB%AC%B4%EC%B2%98%EB%A6%AC+%EA%B7%9C%EC%A0%95&joEfYd=&bylCls=BE&bylClsCd=BE&bylEfYd=&bylNo=0003&admRulSeq=0)

## Project Structure

```
backend/            # Flask API -- see backend/README-en.md for a full file-by-file breakdown
├── data/           # Raw PDFs, parsed JSONs, evaluation test sets
├── pipeline/       # Parsing → Chunking → Tagging → Embedding
├── retrieval/      # BM25 / Dense / Hybrid / Reranker logic
├── classifier/     # Rule-based intent/user-type classifier
├── generation/      # Gemini API answer generation + citation parsing
├── routes/         # Flask API endpoints
├── db/             # MongoDB connection setup
├── evaluation/     # RAGAS-based quantitative evaluation
└── tests/          # pytest unit tests

frontend/           # Next.js (App Router) + TypeScript + Tailwind + next-intl --
                     # see frontend/README-en.md for a full file-by-file breakdown
scripts/            # currently empty placeholders (setup_db.py, run_pipeline.py) --
                     # the actual pipeline scripts live under backend/pipeline/
docs/               # Architecture deep-dives & evaluation reports
```

## Getting Started

### Prerequisites
- Python 3.12+
- A [MongoDB Atlas](https://www.mongodb.com/atlas) cluster (the free M0 tier
  works fine — Atlas Vector Search is available on it too) and its connection
  string
- A [Google AI Studio](https://aistudio.google.com/apikey) API key (free
  tier, no card required)

### 1. Configure environment
```bash
cd backend
cp .env.example .env   # fill in GOOGLE_API_KEY and MONGO_URI
```

### 2. Install dependencies
```bash
pip install -r requirements.txt --break-system-packages
```

### 3. Load the law corpus into MongoDB (one-time)
Embeds the 272 parsed law chunks and creates the Atlas Vector Search index
that hybrid retrieval actually queries at runtime:
```bash
python pipeline/load_to_mongo.py
```
Index build can take a minute or two on Atlas; the script waits until it's
queryable before exiting.

### 4. Start the backend
```bash
python app.py
```
The API is served at http://localhost:5001. The first request is slow since
the embedding/reranker models load lazily on first use.

### 5. Start the frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000 (redirects to `/ko`). Details on the frontend's
structure, next-intl setup, and known caveats are in
[`frontend/README-en.md`](frontend/README-en.md).

## API Reference

Base URL: `http://localhost:5001`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/query` | Ask a question -- runs intent classification → hybrid retrieval → rerank → (if confident) a Gemini-generated answer |
| POST | `/api/feedback` | Record a 👍/👎 (+ optional comment) on a previous `/api/query` response |
| POST | `/api/profile` | Save/update a session's declared user type (e.g. 영주권자) |
| GET | `/api/profile/<session_id>` | Fetch a session's declared user type |

```bash
# Ask a question
curl -X POST http://localhost:5001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "영주권자인데 입영연기 신청 언제까지 해야 하나요?", "session_id": "optional-uuid"}'

# Submit feedback on an answer
curl -X POST http://localhost:5001/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "question": "...", "rating": "up", "comment": "optional"}'

# Save the session's user type
curl -X POST http://localhost:5001/api/profile \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "user_type": "영주권자"}'

# Fetch the session's user type
curl http://localhost:5001/api/profile/<session_id>
```

`user_type` must be one of `영주권자`, `재외동포2세`, `이중국적자`, `유학생`, `기타`.
`rating` (for `/api/feedback`) must be `up` or `down`.

## Evaluation Results
Quantitative evaluation metrics (including retrieval accuracy, answer faithfulness, etc.) are thoroughly documented in [`docs/eval_results-en.md`](docs/eval_results-en.md).

## Development Logs
Development logs for the project are available in [`docs/devlog-en.md`](docs/devlog-en.md)

---

## License

The statutory texts and legal documents used in this project are public government works free of copyright restrictions. The source code is authored for personal portfolio and educational purposes.
