// Shared amber advisory box -- used for both low_confidence's notice and
// the new answer_error state (retrieval succeeded, generation failed).
export default function AdvisoryNotice({ text }: { text: string }) {
  return (
    <div
      style={{
        background: "var(--lowconf-bg)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid var(--lowconf-border)",
        borderLeft: "4px solid #C98A12",
        boxShadow: "0 6px 18px rgba(201,138,18,0.08)",
        borderRadius: 10,
        padding: "13px 16px",
        fontSize: 13,
        lineHeight: 1.65,
        color: "var(--lowconf-text)",
      }}
    >
      {text}
    </div>
  );
}
