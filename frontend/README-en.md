# Frontend — DutyCompass Next.js App

> 한국어 버전: [README.md](README.md)

A port of a Claude Design prototype (`DutyCompass_dc.html`, a mock-data
proof of concept running on its own DSL runtime) into Next.js (App Router) +
TypeScript + Tailwind CSS, wired to the real backend (`POST /api/query`)
instead of the mock. See the "Stage 7" entry in `docs/devlog-en.md` for the
porting background/design decisions, and
[`../backend/README-en.md`](../backend/README-en.md) for the backend
response schema.

## Directory layout

```
frontend/
├── app/[locale]/         # App Router pages (locale-prefixed: /ko, /en)
│   ├── layout.tsx          # root layout -- NextIntlClientProvider, Pretendard font
│   └── page.tsx              # renders <ChatApp/>
├── components/             # 17 React components
├── hooks/                    # useChatSession / useTypewriter / useAnswerReveal
├── lib/                        # theme / api / mapResponse / types / constants / styleHelpers
├── i18n/                        # next-intl routing + request config
├── messages/                     # ko.json / en.json (en is currently a copy of ko, not translated)
├── proxy.ts                       # Next.js 16's middleware (renamed from middleware.ts)
└── next.config.ts                  # wraps the next-intl plugin
```

## components/

| File | Role |
|---|---|
| `ChatApp.tsx` | Top-level client component; owns all state via the single `useChatSession` hook |
| `ThemeRoot.tsx` | Root wrapper that injects CSS custom properties as inline style based on `dark` state |
| `BackgroundBlobs.tsx` | 3 decorative blurred background shapes |
| `Header.tsx` | Logo/title, dark-mode toggle, KO/EN pill (+ "coming soon" tooltip), disclaimer text |
| `MessageList.tsx` | Scroll container; renders the empty state or the message list |
| `EmptyState.tsx` | Empty-conversation state -- heading/subtext + 3 sample-question chips |
| `MessageItem.tsx` | Per-message render switch across loading/error/empty/oos/lowConf/normal |
| `UserBubble.tsx` | User's question bubble |
| `LoadingStages.tsx` | 4-stage loading animation with per-stage typing effect |
| `ErrorCard.tsx` | Retry card on network failure |
| `EmptyResultCard.tsx` | "No matching articles" notice |
| `OosCard.tsx` | Out-of-scope message + related articles (if any) |
| `AdvisoryNotice.tsx` | Shared amber advisory box for low_confidence and `answer_error` |
| `TagRow.tsx` | user_type_tags/topic_tags pills |
| `AnswerCard.tsx` | Answer text + citation chips, with a progressive reveal animation |
| `CitationChip.tsx` | Clickable citation chip (renders as inert text when result_index is null) |
| `EvidenceToggleButton.tsx` | "Show/hide N evidence articles" toggle |
| `EvidenceCard.tsx` / `EvidenceCardList.tsx` | Evidence-article cards (shared "ranked"/"related" variants) |
| `InputBar.tsx` | Bottom text input + send button |

## hooks/

- **`useChatSession.ts`**: the central state machine, managing the message
  array via `useReducer`. On submit, fires `queryApi()` immediately while
  running the 4-stage loading animation in parallel; if the response arrives
  fast (e.g. out-of-scope), the stages snap to fully-checked and hold
  briefly before applying the result, otherwise it applies immediately once
  already at the last stage -- designed to avoid a static screen for several
  seconds. Also owns `input`/`highlightedKey`/`showEnHint`/`dark` state and
  `scrollToCard` (citation click -> scroll + highlight).
- **`useTypewriter.ts`**: per-character typing reveal (used for loading-stage labels).
- **`useAnswerReveal.ts`**: the answer-reveal animation, counting a citation
  as 1 unit and text as 1 unit per character.

Both hooks handle their reset via React's "state adjustment during render"
pattern rather than calling setState inside the effect body, per the React
Compiler's `set-state-in-effect` lint rule.

## lib/

- **`theme.ts`**: `DutyCompass_dc.html`'s `THEMES.light`/`THEMES.dark` color
  tokens (~45 vars × 2 themes) ported verbatim. Kept as CSS-var inline
  injection rather than moved to Tailwind `dark:` classes -- the source
  already references everything via `var(--xxx)`, and hand-transcribing ~90
  color values into two places is exactly the kind of typo-prone work worth
  avoiding.
- **`constants.ts`**: typing/reveal/highlight timing constants (all matching the original values).
- **`styleHelpers.ts`**: loading-stage circle/label styles, evidence-card relevance dots.
- **`api.ts`**: `queryApi()` -- fetch wrapper unifying network failures and non-2xx responses into `ApiError`.
- **`types.ts`**: the backend `/api/query` response schema plus the frontend view-model types.
- **`mapResponse.ts`**:
  - `mapResponseToViewModel`: 5-way branch across `out_of_scope` /
    `low_confidence` / empty results / **`answer_error`** (a new state --
    retrieval succeeded but generation failed) / normal.
  - `mapAnswerSegments`: maps the backend's `answer_segments` to the
    frontend's `answerParts`.
  - `formatArticleLabel`: the single formatter shared by evidence-card
    titles and citation chip labels. For table (별표) sources, `law_name`
    already contains "별표 N", so it isn't appended again -- an earlier pass
    missed this and rendered a visible duplicate ("병역법 시행령 별표 3
    별표3"), caught during real screenshot verification and fixed.
  - `rankRelevance`: a per-message relative ranking (only the top result is
    "high", the rest "medium") -- an intentionally temporary heuristic,
    since the backend's raw scores aren't comparable across questions (see
    `docs/eval_results-en.md`).

## i18n/ + messages/

next-intl's App Router setup (`i18n/routing.ts`, `i18n/request.ts`,
`proxy.ts`). `localePrefix: "always"` keeps `/ko` and `/en` symmetric from
day one, so there's no "default locale has no prefix" special case to unwind later.

**`messages/en.json` is currently a literal copy of `ko.json` (not
translated)** -- per the porting instructions, the EN button only needs to
show a "English version coming soon" tooltip for now; the next-intl routing
structure was scaffolded now specifically so it won't need refactoring later.
Real English translations are follow-up work.

**A caveat on `messages/ko.json`**: the Korean text in the porting source
(`DutyCompass_dc.html`, `mock-data.js`) arrived with corrupted encoding, so
a good number of UI strings (header subtitle, empty-state copy, loading-stage
labels, etc.) were reconstructed via pattern-matching. Strings directly
quoted in the porting instructions were confirmed to match exactly, but the
whole file is worth a proofread pass.

## Next.js 16 notes

- `middleware.ts` is deprecated in Next.js 16 and renamed to `proxy.ts` (the
  export name changes from `middleware` to `proxy` too) -- this project was
  written with `proxy.ts` from the start.
- `AGENTS.md`/`CLAUDE.md` are auto-generated by Next.js on `next dev`/`next
  build` (a notice that this version has breaking changes and to read the
  bundled local docs first) -- left in place since they regenerate on the
  next run regardless.

## Running it

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000, auto-redirects to /ko
```

The backend (`cd backend && python app.py`, port 5001) needs to be running
too for real answers. The API base URL comes from `.env.local`'s
`NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:5001`).

```bash
npm run build   # production build + type check
npm run lint     # ESLint (includes React Compiler rules)
```
