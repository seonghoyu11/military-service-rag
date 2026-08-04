"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import type { ChatMessage } from "@/hooks/useChatSession";
import AdvisoryNotice from "./AdvisoryNotice";
import AnswerCard from "./AnswerCard";
import EmptyResultCard from "./EmptyResultCard";
import ErrorCard from "./ErrorCard";
import EvidenceCardList from "./EvidenceCardList";
import EvidenceToggleButton from "./EvidenceToggleButton";
import LoadingStages from "./LoadingStages";
import OosCard from "./OosCard";
import TagRow from "./TagRow";
import UserBubble from "./UserBubble";

export default function MessageItem({
  message,
  dark,
  highlightedKey,
  onRetry,
  onCite,
}: {
  message: ChatMessage;
  dark: boolean;
  highlightedKey: string | null;
  onRetry: (question: string) => void;
  onCite: (msgId: string, refIndex: number) => void;
}) {
  const t = useTranslations();
  // Evidence-list open/closed state -- local to this message, never
  // centralized, since it's purely about this one message's own render
  // (matches the Stage 7 plan's deliberate deviation from the DC
  // prototype's central `revealed` map).
  const [revealed, setRevealed] = useState(false);

  const handleCite = (refIndex: number) => {
    // Clicking a citation must reveal the evidence list even if it was
    // collapsed, on top of the scroll+highlight -- easy to lose if these
    // two effects aren't kept together.
    setRevealed(true);
    onCite(message.id, refIndex);
  };

  const response = message.response;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <UserBubble question={message.question} />

      {message.status === "loading" && (
        <LoadingStages loadingStage={message.loadingStage} dark={dark} />
      )}

      {message.status === "error" && <ErrorCard onRetry={() => onRetry(message.question)} />}

      {message.status === "done" && response?.type === "empty" && <EmptyResultCard />}

      {message.status === "done" && response?.type === "oos" && (
        <OosCard
          message={response.message}
          relatedScopeInfo={response.relatedScopeInfo}
          msgId={message.id}
          dark={dark}
          highlightedKey={highlightedKey}
        />
      )}

      {message.status === "done" && response?.type === "lowConf" && (
        <>
          <AdvisoryNotice text={response.notice} />
          <TagRow
            userTags={response.intent.user_type_tags}
            topicTags={response.intent.topic_tags}
          />
          {/* low_confidence results are always shown, no toggle -- distinct
              from the "normal" case below, do not collapse the two. */}
          <EvidenceCardList
            items={response.results}
            msgId={message.id}
            variant="ranked"
            dark={dark}
            highlightedKey={highlightedKey}
            label={t("evidence.label")}
          />
        </>
      )}

      {message.status === "done" && response?.type === "normal" && (
        <>
          <TagRow
            userTags={response.intent.user_type_tags}
            topicTags={response.intent.topic_tags}
          />
          {response.hasAnswerError ? (
            <AdvisoryNotice text={t("answerError.message")} />
          ) : (
            <AnswerCard parts={response.answerParts} onCite={handleCite} />
          )}
          {response.results.length > 0 && (
            <EvidenceToggleButton
              count={response.results.length}
              revealed={revealed}
              onClick={() => setRevealed((r) => !r)}
            />
          )}
          {revealed && (
            <EvidenceCardList
              items={response.results}
              msgId={message.id}
              variant="ranked"
              dark={dark}
              highlightedKey={highlightedKey}
            />
          )}
        </>
      )}
    </div>
  );
}
