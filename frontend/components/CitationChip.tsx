export default function CitationChip({
  label,
  refIndex,
  onClick,
}: {
  label: string;
  refIndex: number | null;
  onClick: (refIndex: number) => void;
}) {
  const baseStyle = {
    display: "inline-flex" as const,
    alignItems: "center" as const,
    background: "var(--cite-bg)",
    backdropFilter: "blur(6px)",
    border: "1px solid var(--cite-border)",
    color: "var(--cite-text)",
    fontSize: 12.5,
    fontWeight: 700,
    padding: "1px 9px",
    borderRadius: 999,
    margin: "0 2px",
    verticalAlign: "middle" as const,
  };

  // refIndex is null when the backend couldn't match this citation phrase
  // to a result -- render the label without making it clickable, don't
  // crash.
  if (refIndex === null) {
    return <span style={baseStyle}>{label}</span>;
  }

  return (
    <span
      className="dc-cite"
      onClick={() => onClick(refIndex)}
      style={{ ...baseStyle, cursor: "pointer" }}
    >
      {label}
    </span>
  );
}
