import { linkifyText } from "@/lib/mapResponse";

// Renders OOS fallback messages with any embedded URL (e.g. the MMA
// recruitment-notice links in classifier/model.py's OUT_OF_SCOPE_CATEGORIES)
// as a clickable link, instead of dead plain text.
export default function LinkifiedText({ text }: { text: string }) {
  const parts = linkifyText(text);

  return (
    <>
      {parts.map((part, i) =>
        part.isLink ? (
          <a
            key={i}
            href={part.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "inherit", textDecoration: "underline" }}
          >
            {part.url}
          </a>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  );
}
