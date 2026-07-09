# Military Service RAG Chatbot for Overseas Conscripts

An LLM (RAG)-based chatbot designed to provide administrative guidance on military service for overseas Korean conscripts, including permanent residents, international students, dual citizens, and second-generation overseas South Koreans.

> **한국인들을 위한 알림**:
> 한국어로 된 README는 [README.md](README.md)를 참고하십시오.

> **⚠️⚠️ Disclaimer**
> This project was developed solely for personal learning and portfolio purposes and is NOT an official service of the Military Manpower Administration (MMA). 
> The responses provided by this chatbot are for informational purposes only, not legal advice. 
> For official decisions regarding military service, please consult the MMA (+82-1588-9090), regional MMA offices, or your local Korean Embassy/Consulate.

---


## Project Overview
The South Korean Military Service Act features highly complex cross-references between clauses, and exception clauses vary significantly based on the user's status (e.g., permanent resident, international student, dual citizen, or second-generation overseas Korean). Rather than relying on simple LLM prompting, this project implements a highly structured pipeline to maximize retrieval accuracy:

- Structured Parsing & Chunking: Preserves the hierarchical document structure (Article/Paragraph/Item) of legal texts.
- Intent Classifier: Classifies user types and question intent upfront as a primary filter.
- BM25 + Dense Embedding Hybrid Search
- Reranker: Sorts and optimizes the final retrieved source articles.
- Claude API: Generates responses that include precise citations of the supporting articles.
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
                     [Claude API (Haiku 4.5)]
```

For a detailed walkthrough, please refer to [`docs/architecture.md`](docs/architecture.md).

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
| LLM | Anthropic API (Claude Haiku 4.5) |
| Frontend | Next.js, next-intl (영/한 토글) |
| Evaluation | RAGAS |

---

## Data Sources

The following documents are public government works collected from the [National Legal Information Center](law.go.kr) of Republic of Korea. Documents are written in Korean, and English translated documents are available in this [link](https://www.law.go.kr/engLsSc.do?menuId=1&subMenuId=21&tabMenuId=117).

- [Military Service Act](https://www.law.go.kr/법령/병역법)
- [Enforcement Decree of the Military Service Act](https://www.law.go.kr/법령/병역법시행령)
- [Enforcement Rule of the Military Service Act](https://www.law.go.kr/법령/병역법시행규칙)
- [Regulations on Overseas Travel of Military Conscripts (MMA Directive)](https://www.law.go.kr/행정규칙/병역의무자국외여행업무처리규정/(2141,20250502))
- [Directive on Leave and Return Expenses for Enlisted Permanent Residents (MND Directive)](https://www.law.go.kr/행정규칙/국외영주권자등병복무시휴가여비및전역시귀가여비지급훈령/(2414,20200413))
- [[Table 3] Overseas Travel Permission or Extension for Emigration Purposes](https://www.law.go.kr/LSW/admRulBylInfoPLinkR.do?bylBrNo=00&admRulNm=%EB%B3%91%EC%97%AD%EC%9D%98%EB%AC%B4%EC%9E%90+%EA%B5%AD%EC%99%B8%EC%97%AC%ED%96%89+%EC%97%85%EB%AC%B4%EC%B2%98%EB%A6%AC+%EA%B7%9C%EC%A0%95&joEfYd=&bylCls=BE&bylClsCd=BE&bylEfYd=&bylNo=0003&admRulSeq=0)

## Project Structure

```
backend/
├── data/           # Raw PDFs, parsed JSONs, evaluation test sets
├── pipeline/       # Parsing → Chunking → Tagging → Embedding
├── retrieval/      # BM25 / Dense / Hybrid / Reranker logic
├── classifier/     # Intent classifier training and inference
├── llm/            # Claude API integration wrapper
├── routes/         # Flask API endpoints
├── db/             # MongoDB connection setup
└── evaluation/     # RAGAS-based quantitative evaluation

frontend/           # Next.js App (Chat UI, User Profiles, EN/KO Toggle)
scripts/            # DB configuration & pipeline execution scripts
docs/               # Architecture deep-dives & evaluation reports
```

## Getting Started

```bash
# Backend
cd backend
pip install -r requirements.txt --break-system-packages
cp .env.example .env   # Fill in your ANTHROPIC_API_KEY and MONGO_URI
python app.py

# Frontend
cd frontend
npm install
npm run dev
```

## Evaluation Results
Quantitative evaluation metrics (including retrieval accuracy, answer faithfulness, etc.) are thoroughly documented in [docs/eval_results.md](docs/eval_results.md).

---

## License

The statutory texts and legal documents used in this project are public government works free of copyright restrictions. The source code is authored for personal portfolio and educational purposes.