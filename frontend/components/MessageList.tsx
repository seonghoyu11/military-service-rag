import type { RefObject } from "react";

import type { ChatMessage } from "@/hooks/useChatSession";
import EmptyState from "./EmptyState";
import MessageItem from "./MessageItem";

export default function MessageList({
  containerRef,
  messages,
  isEmpty,
  dark,
  highlightedKey,
  onSampleQuestion,
  onRetry,
  onCite,
}: {
  containerRef: RefObject<HTMLDivElement | null>;
  messages: ChatMessage[];
  isEmpty: boolean;
  dark: boolean;
  highlightedKey: string | null;
  onSampleQuestion: (question: string) => void;
  onRetry: (question: string) => void;
  onCite: (msgId: string, refIndex: number) => void;
}) {
  return (
    <div
      ref={containerRef}
      style={{ position: "relative", zIndex: 1, flex: 1, minHeight: 0, overflowY: "auto", padding: "22px 20px 24px" }}
    >
      <div style={{ maxWidth: 760, margin: "0 auto", display: "flex", flexDirection: "column", gap: 30 }}>
        {isEmpty && <EmptyState onPick={onSampleQuestion} />}
        {messages.map((m) => (
          <MessageItem
            key={m.id}
            message={m}
            dark={dark}
            highlightedKey={highlightedKey}
            onRetry={onRetry}
            onCite={onCite}
          />
        ))}
      </div>
    </div>
  );
}
