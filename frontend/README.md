# Frontend — DutyCompass Next.js 앱

> English version: [README-en.md](README-en.md)

Claude Design 프로토타입(`DutyCompass_dc.html`, 자체 런타임 기반 목업)을
Next.js(App Router) + TypeScript + Tailwind CSS로 포팅하고, 목업 대신 실제
백엔드(`POST /api/query`)에 연결한 채팅형 UI. 포팅 배경/설계 근거는
`docs/devlog.md`의 "Stage 7" 항목, 백엔드 응답 스키마는
[`../backend/README.md`](../backend/README.md) 참고.

## 디렉토리 구조

```
frontend/
├── app/[locale]/         # App Router 페이지 (locale prefix: /ko, /en)
│   ├── layout.tsx          # 루트 레이아웃 — NextIntlClientProvider, Pretendard 폰트
│   └── page.tsx              # <ChatApp/> 렌더링
├── components/             # React 컴포넌트 17개
├── hooks/                    # useChatSession / useTypewriter / useAnswerReveal
├── lib/                        # theme / api / mapResponse / types / constants / styleHelpers
├── i18n/                        # next-intl 라우팅 + 요청 설정
├── messages/                     # ko.json / en.json (en은 현재 ko 그대로 복사, 번역 미착수)
├── proxy.ts                       # Next.js 16의 미들웨어 (middleware.ts에서 개명됨)
└── next.config.ts                  # next-intl 플러그인 래핑
```

## components/

| 파일 | 역할 |
|---|---|
| `ChatApp.tsx` | 최상위 클라이언트 컴포넌트. `useChatSession` 훅 하나로 전체 상태 소유 |
| `ThemeRoot.tsx` | `dark` 상태에 따라 CSS 커스텀 프로퍼티를 inline style로 주입하는 루트 래퍼 |
| `BackgroundBlobs.tsx` | 장식용 blur 배경 3개 |
| `Header.tsx` | 로고/타이틀, 다크모드 토글, KO/EN pill(+ "준비 중" 툴팁), 안내 문구 |
| `MessageList.tsx` | 스크롤 컨테이너, 빈 상태/메시지 목록 렌더 |
| `EmptyState.tsx` | 빈 대화 상태 — 안내 문구 + 샘플 질문 칩 3개 |
| `MessageItem.tsx` | 메시지 1건의 상태(loading/error/empty/oos/lowConf/normal)별 렌더 분기 |
| `UserBubble.tsx` | 사용자 질문 말풍선 |
| `LoadingStages.tsx` | 4단계 로딩 애니메이션(단계별 타이핑 효과) |
| `ErrorCard.tsx` | 네트워크 오류 시 재시도 카드 |
| `EmptyResultCard.tsx` | 검색 결과 0건 안내 |
| `OosCard.tsx` | 스코프 밖 질문 안내 + 관련 조항(있으면) |
| `AdvisoryNotice.tsx` | 저신뢰/`answer_error` 공용 amber 안내 박스 |
| `TagRow.tsx` | user_type_tags/topic_tags 필 |
| `AnswerCard.tsx` | 답변 텍스트 + citation 칩, 점진적 reveal 애니메이션 |
| `CitationChip.tsx` | 클릭 가능한 인용 칩 (result_index가 null이면 비활성 텍스트) |
| `EvidenceToggleButton.tsx` | "근거 조항 N건 보기/숨기기" 토글 |
| `EvidenceCard.tsx` / `EvidenceCardList.tsx` | 근거 조항 카드(ranked/related variant 공용) |
| `InputBar.tsx` | 하단 입력창 + 전송 버튼 |

## hooks/

- **`useChatSession.ts`**: 메시지 배열을 `useReducer`로 관리하는 중앙 상태머신.
  질문 제출 시 `queryApi()`를 즉시 fetch하면서 동시에 로딩 4단계 애니메이션을
  진행시키고, 응답이 빨리 오면(OOS 등) 단계를 스냅해서 잠깐 붙잡았다가
  적용, 이미 마지막 단계면 즉시 적용 — "몇 초간 정적인 화면"을 피하기 위한
  설계. `input`/`highlightedKey`/`showEnHint`/`dark` 상태와 `scrollToCard`
  (citation 클릭 → 스크롤+하이라이트)도 이 훅이 소유.
- **`useTypewriter.ts`**: 글자 단위 타이핑 reveal(로딩 단계 라벨용).
- **`useAnswerReveal.ts`**: citation을 1유닛, 텍스트는 글자수만큼 유닛으로 세는
  답변 reveal 애니메이션.

두 훅 다 React Compiler의 `set-state-in-effect` lint 규칙 때문에, 리셋은
"렌더 중 상태 조정" 패턴으로 처리(이펙트 안에서 직접 setState 안 함).

## lib/

- **`theme.ts`**: `DutyCompass_dc.html`의 `THEMES.light`/`THEMES.dark` 색상
  토큰(~45개 × 2테마)을 그대로 포팅. Tailwind `dark:` 클래스로 옮기지 않고
  CSS 변수 inline 주입 방식을 그대로 유지 — 원본이 전부 `var(--xxx)`
  참조라 90개 색상값을 손으로 두 번 옮겨적는 오류 위험을 피하기 위함.
- **`constants.ts`**: 타이핑/reveal/하이라이트 타이밍 상수(전부 원본 값 그대로).
- **`styleHelpers.ts`**: 로딩 단계 원/라벨 스타일, 근거 카드 relevance dot 계산.
- **`api.ts`**: `queryApi()` — fetch 래퍼, 네트워크 실패/비2xx를 `ApiError`로 통일.
- **`types.ts`**: 백엔드 `/api/query` 응답 스키마 + 프론트 뷰모델 타입.
- **`mapResponse.ts`**:
  - `mapResponseToViewModel`: `out_of_scope`/`low_confidence`/빈 결과/
    **`answer_error`(신규 상태 — 검색은 성공, 생성만 실패)**/정상, 5분기 매핑.
  - `mapAnswerSegments`: 백엔드 `answer_segments` → 프론트 `answerParts`.
  - `formatArticleLabel`: 근거 카드 제목과 citation 칩 라벨이 공유하는 단일
    포맷 함수. 별표(article_no가 "별표"로 시작) 케이스는 `law_name` 필드
    자체에 이미 "별표 N"이 포함돼 있어서 별도로 안 붙임 — 처음엔 이걸 놓쳐서
    "병역법 시행령 별표 3 별표3"로 중복 렌더링되는 버그가 있었고, 실제
    스크린샷 검증 중 발견해서 수정함.
  - `rankRelevance`: 메시지 내 상대적 순위(1위만 high, 나머지 medium) —
    백엔드 원점수가 질문 간 비교 불가능하다는 `docs/eval_results.md`의
    발견에 근거한 임시 휴리스틱.

## i18n/ + messages/

next-intl App Router 셋업(`i18n/routing.ts`, `i18n/request.ts`, `proxy.ts`).
`localePrefix: "always"`라 `/ko`, `/en` 둘 다 항상 prefix가 붙음 — 나중에
"기본 locale은 prefix 없음" 같은 특수 분기를 안 풀어도 되게 하려는 선택.

**`messages/en.json`은 현재 `ko.json`을 그대로 복사한 상태다(번역 안 됨)** —
지시서상 이번 포팅에서는 EN 버튼이 "영문 버전은 준비 중이에요" 툴팁만
띄우면 되고, next-intl 라우팅 구조는 나중에 리팩터링 안 해도 되게 지금
잡아두는 게 목적이었음. 실제 영문 번역은 후속 작업.

**`messages/ko.json` 관련 주의**: 포팅 원본(`DutyCompass_dc.html`,
`mock-data.js`)의 한글 텍스트가 전달 과정에서 인코딩이 깨진 상태였어서,
UI 문자열 상당수(헤더 부제, 빈 상태 문구, 로딩 단계명 등)를 패턴 매칭으로
역추정 복원했다. 지시서에 직접 인용된 문자열은 정확히 일치 확인했지만,
전체를 한 번 검수해보는 걸 권장.

## Next.js 16 관련 메모

- `middleware.ts`가 Next.js 16에서 deprecated되고 `proxy.ts`로 이름이
  바뀜(export도 `middleware`→`proxy`) — 이 프로젝트는 처음부터 `proxy.ts`로 작성.
- `AGENTS.md`/`CLAUDE.md`는 Next.js가 `next dev`/`next build` 실행 시 자동
  생성하는 파일("이 버전은 breaking change가 있으니 로컬 문서부터 읽어라"는
  안내) — 지워도 다음 실행 때 재생성되므로 그대로 둠.

## 실행

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000, 자동으로 /ko 로 리다이렉트
```

백엔드(`cd backend && python app.py`, 포트 5001)가 같이 떠 있어야 실제
질문에 답변을 받을 수 있다. API 베이스 URL은 `.env.local`의
`NEXT_PUBLIC_API_BASE_URL`(기본값 `http://localhost:5001`).

```bash
npm run build   # 프로덕션 빌드 + 타입체크
npm run lint     # ESLint (React Compiler 관련 규칙 포함)
```
