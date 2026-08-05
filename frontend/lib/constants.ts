// Timing constants ported verbatim from DutyCompass.dc.html's Component
// class (typeStage/typeAnswer/runLoading/scrollToCard).

export const STAGE_INTERVAL_MS = 650; // gap between loading-stage advances
export const TYPE_CHAR_MS = 45; // per-character typing speed for stage labels
export const ANSWER_REVEAL_TICK_MS = 16; // answer reveal animation tick
export const ANSWER_REVEAL_UNITS_PER_TICK = 2; // units revealed per tick
export const HIGHLIGHT_MS = 1800; // evidence-card highlight duration after citation click
export const FAST_FORWARD_HOLD_MS = 300; // hold fully-checked stages before applying a fast result

export const STAGE_COUNT = 4;
