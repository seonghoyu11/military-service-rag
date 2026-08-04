"use client";

import { useChatSession } from "@/hooks/useChatSession";
import BackgroundBlobs from "./BackgroundBlobs";
import Header from "./Header";
import InputBar from "./InputBar";
import MessageList from "./MessageList";
import ThemeRoot from "./ThemeRoot";

export default function ChatApp() {
  const {
    messages,
    input,
    setInput,
    submit,
    submitText,
    retry,
    highlightedKey,
    showEnHint,
    tryEn,
    dark,
    toggleDark,
    containerRef,
    scrollToCard,
  } = useChatSession();

  const isLoadingAny = messages.some((m) => m.status === "loading");

  return (
    <ThemeRoot dark={dark}>
      <BackgroundBlobs />
      <Header dark={dark} onToggleDark={toggleDark} showEnHint={showEnHint} onTryEn={tryEn} />
      <MessageList
        containerRef={containerRef}
        messages={messages}
        isEmpty={messages.length === 0}
        dark={dark}
        highlightedKey={highlightedKey}
        onSampleQuestion={submitText}
        onRetry={retry}
        onCite={scrollToCard}
      />
      <InputBar
        value={input}
        onChange={setInput}
        onSubmit={submit}
        disabled={isLoadingAny}
        dark={dark}
      />
    </ThemeRoot>
  );
}
