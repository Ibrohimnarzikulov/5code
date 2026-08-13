/** Bitta xabar va uning bloklari (matn, fikrlash, tool, artifact). */

import { renderMarkdown } from "../markdown";

export function ArtifactChip({ artifact, onOpen }) {
  return (
    <button className="artifact-chip" onClick={() => onOpen(artifact)}>
      <span className="glyph">◫</span>
      <span className="grow">
        <b>{artifact.title}</b>
        <small>v{artifact.version} · bir faylli HTML sayt</small>
      </span>
      <span className="cta">Ochish →</span>
    </button>
  );
}

function Thinking({ text }) {
  return (
    <details className="think">
      <summary>◇ fikrlash</summary>
      {text}
    </details>
  );
}

function ToolCard({ name, input }) {
  const args = typeof input === "string" ? input : JSON.stringify(input, null, 2);
  return (
    <div className="tool">
      <div className="tool-head">⚡ {name}</div>
      <pre>{args}</pre>
    </div>
  );
}

function ToolResult({ name, content, isError }) {
  return (
    <div className={`tool${isError ? " err" : ""}`}>
      <div className="tool-head">
        {isError ? "⚠︎" : "✓"} {name} natijasi
      </div>
      <pre>{content}</pre>
    </div>
  );
}

function Markdown({ text }) {
  return <div dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />;
}

/** tool_result blokidan matn ajratadi (string yoki bloklar ro'yxati). */
function resultText(block) {
  if (Array.isArray(block.content)) {
    return block.content.map((part) => part.text ?? "").join("\n");
  }
  return String(block.content ?? "");
}

/**
 * @param {{message: {role: string, content: any}, onOpenArtifact: Function}} props
 */
export default function Message({ message, onOpenArtifact }) {
  const { role, content } = message;

  // Oddiy matnli xabar (foydalanuvchi)
  if (typeof content === "string") {
    return (
      <div className={`msg ${role}`}>
        <div className="who">{role === "user" ? "S" : "C"}</div>
        <div className="body">
          <Markdown text={content} />
        </div>
      </div>
    );
  }

  if (!Array.isArray(content) || content.length === 0) return null;

  // Faqat tool natijalaridan iborat "user" xabari — assistant tomonida ko'rsatamiz
  const onlyResults =
    role === "user" && content.every((b) => b.type === "tool_result");

  return (
    <div className={`msg ${onlyResults ? "assistant" : role}`}>
      <div className="who">{onlyResults || role === "assistant" ? "C" : "S"}</div>
      <div className="body">
        {content.map((block, index) => {
          const key = block.id ?? block.tool_use_id ?? index;

          if (block.type === "text" && block.text) {
            return <Markdown key={key} text={block.text} />;
          }
          if (block.type === "thinking" && block.thinking) {
            return <Thinking key={key} text={block.thinking} />;
          }
          if (block.type === "tool_use") {
            // Artifact tool'lari chip sifatida alohida ko'rsatiladi
            if (block.name?.endsWith("_artifact")) return null;
            return <ToolCard key={key} name={block.name} input={block.input} />;
          }
          if (block.type === "tool_result") {
            if (block.name?.endsWith("_artifact")) return null;
            return (
              <ToolResult
                key={key}
                name={block.name ?? "tool"}
                content={resultText(block)}
                isError={Boolean(block.is_error)}
              />
            );
          }
          if (block.type === "artifact") {
            return (
              <ArtifactChip
                key={key}
                artifact={block}
                onOpen={onOpenArtifact}
              />
            );
          }
          return null;
        })}
      </div>
    </div>
  );
}
