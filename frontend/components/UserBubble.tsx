export default function UserBubble({ question }: { question: string }) {
  return (
    <div
      style={{
        alignSelf: "flex-end",
        maxWidth: "85%",
        background: "linear-gradient(160deg, rgba(46,64,102,0.88), rgba(18,29,52,0.92))",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        border: "1px solid var(--bubble-border)",
        boxShadow: "0 6px 16px var(--bubble-shadow), inset 0 1px 0 rgba(255,255,255,0.15)",
        color: "#fff",
        padding: "11px 16px",
        borderRadius: "16px 16px 4px 16px",
        fontSize: 14.5,
        lineHeight: 1.55,
      }}
    >
      {question}
    </div>
  );
}
