export default function TagRow({
  userTags,
  topicTags,
}: {
  userTags: string[];
  topicTags: string[];
}) {
  if (userTags.length + topicTags.length === 0) return null;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {userTags.map((tag, i) => (
        <div
          key={`u-${i}`}
          style={{
            background: "var(--tag-user-bg)",
            backdropFilter: "blur(8px)",
            color: "var(--tag-user-text)",
            fontSize: 11.5,
            padding: "3px 10px",
            borderRadius: 999,
          }}
        >
          {tag}
        </div>
      ))}
      {topicTags.map((tag, i) => (
        <div
          key={`t-${i}`}
          style={{
            background: "var(--tag-topic-bg)",
            backdropFilter: "blur(8px)",
            color: "var(--tag-topic-text)",
            fontSize: 11.5,
            padding: "3px 10px",
            borderRadius: 999,
          }}
        >
          {tag}
        </div>
      ))}
    </div>
  );
}
