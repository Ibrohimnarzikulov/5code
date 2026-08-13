/** Chat sahifasi — suhbatlar, streaming javob, artifact paneli. */

import { useCallback, useEffect, useRef, useState } from "react";

import { api, streamChat } from "../api";
import ArtifactPanel from "../components/ArtifactPanel";
import Message from "../components/Message";
import Shell from "../components/Shell";
import { useAuth } from "../context/AuthContext";

const SUGGESTIONS = [
  "Menga portfolio sayt yasab ber, dark tema",
  "FastAPI'da JWT auth qanday yoziladi?",
  "Python'da async retry decorator yoz",
  "Bu papkadagi fayllarni ko'rsat",
];

const MAX_TEXTAREA_HEIGHT = 190;

export default function Chat() {
  const { user, toast } = useAuth();

  const [conversations, setConversations] = useState([]);
  const [currentId, setCurrentId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [artifact, setArtifact] = useState(null);

  // Oqim davomida yig'iladigan joriy javob
  const [live, setLive] = useState(null);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const scrollDown = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  useEffect(scrollDown, [messages, live, scrollDown]);

  const loadConversations = useCallback(async () => {
    try {
      setConversations(await api("/api/conversations"));
    } catch (err) {
      toast(err.message, true);
    }
  }, [toast]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  /** Suhbatni ochadi: xabarlar + unga tegishli artifactlar. */
  const openConversation = useCallback(
    async (id) => {
      setCurrentId(id);
      setLive(null);
      try {
        const [history, artifacts] = await Promise.all([
          api(`/api/conversations/${id}/messages`),
          api("/api/artifacts"),
        ]);

        const chips = artifacts
          .filter((a) => a.conversation_id === id)
          .map((a) => ({ role: "assistant", content: [{ type: "artifact", ...a }] }));

        setMessages([...history, ...chips]);
      } catch (err) {
        toast(err.message, true);
      }
    },
    [toast],
  );

  function newChat() {
    setCurrentId(null);
    setMessages([]);
    setLive(null);
    setArtifact(null);
    inputRef.current?.focus();
  }

  async function removeConversation(id, event) {
    event.stopPropagation();
    if (!confirm("Bu suhbat o'chirilsinmi? Bu qaytarib bo'lmaydi.")) return;
    try {
      await api(`/api/conversations/${id}`, { method: "DELETE" });
      if (currentId === id) newChat();
      await loadConversations();
      toast("Suhbat o'chirildi");
    } catch (err) {
      toast(err.message, true);
    }
  }

  /** Xabar yuborish va SSE oqimini o'qish. */
  async function send(textOverride) {
    const text = (textOverride ?? draft).trim();
    if (!text || streaming) return;

    setDraft("");
    if (inputRef.current) inputRef.current.style.height = "auto";

    setMessages((list) => [...list, { role: "user", content: text }]);
    setStreaming(true);

    // Oqim davomida to'planadigan bloklar
    const blocks = [];
    let textBlock = null;
    let thinkingBlock = null;
    let conversationId = currentId;

    const flush = () => setLive({ role: "assistant", content: [...blocks] });

    try {
      await streamChat({
        conversationId: currentId,
        message: text,
        onEvent: (event) => {
          switch (event.type) {
            case "start":
              conversationId = event.conversation_id;
              if (currentId !== event.conversation_id) {
                setCurrentId(event.conversation_id);
                loadConversations();
              }
              break;

            case "thinking":
              if (!thinkingBlock) {
                thinkingBlock = { type: "thinking", thinking: "" };
                blocks.push(thinkingBlock);
              }
              thinkingBlock.thinking += event.text;
              flush();
              break;

            case "text":
              if (!textBlock) {
                textBlock = { type: "text", text: "" };
                blocks.push(textBlock);
              }
              textBlock.text += event.text;
              flush();
              break;

            case "tool_use":
              blocks.push({
                type: "tool_use",
                id: event.id,
                name: event.name,
                input: event.input,
              });
              textBlock = null;
              flush();
              break;

            case "artifact":
              blocks.push({ type: "artifact", ...event });
              setArtifact(event);
              textBlock = null;
              flush();
              break;

            case "tool_result":
              blocks.push({
                type: "tool_result",
                tool_use_id: event.id,
                name: event.name,
                content: event.content,
                is_error: event.is_error,
              });
              flush();
              break;

            case "error":
              blocks.push({ type: "text", text: `⚠︎ ${event.message}` });
              textBlock = null;
              flush();
              break;

            case "done":
              loadConversations();
              break;

            default:
              break;
          }
        },
      });
    } catch (err) {
      blocks.push({ type: "text", text: `⚠︎ ${err.message}` });
    } finally {
      setMessages((list) => [...list, { role: "assistant", content: blocks }]);
      setLive(null);
      setStreaming(false);
      setCurrentId((id) => id ?? conversationId);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  function autoGrow(event) {
    setDraft(event.target.value);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(
      event.target.scrollHeight,
      MAX_TEXTAREA_HEIGHT,
    )}px`;
  }

  const sidebar = (
    <>
      <button className="btn btn-primary" onClick={newChat}>
        + Yangi suhbat
      </button>

      <div className="conv-list stagger">
        {conversations.length === 0 && (
          <p className="muted small">Hozircha suhbat yo'q</p>
        )}
        {conversations.map((conv) => (
          <button
            key={conv.id}
            className={`conv-item${conv.id === currentId ? " active" : ""}`}
            onClick={() => openConversation(conv.id)}
          >
            <span>{conv.title}</span>
            <span
              className="conv-del"
              title="O'chirish"
              onClick={(e) => removeConversation(conv.id, e)}
            >
              ✕
            </span>
          </button>
        ))}
      </div>
    </>
  );

  const isEmpty = messages.length === 0 && !live;

  return (
    <Shell sidebarExtra={sidebar} wide={Boolean(artifact)}>
      <main className="main glass">
        <header className="chat-head">
          <h2>
            {conversations.find((c) => c.id === currentId)?.title ?? "Yangi suhbat"}
          </h2>
          <div className="status">
            <span className={`dot${streaming ? " pulsing" : ""}`} />
            <span>{streaming ? "yozmoqda…" : "tayyor"}</span>
          </div>
        </header>

        <div className="messages">
          {isEmpty ? (
            <div className="empty">
              <h3>Salom, {user?.username}! 👋</h3>
              <p>Nimadan boshlaymiz?</p>
              <div className="suggestions">
                {SUGGESTIONS.map((item, index) => (
                  <button
                    key={item}
                    style={{ animationDelay: `${0.08 * (index + 1)}s` }}
                    onClick={() => send(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <Message
                  key={index}
                  message={message}
                  onOpenArtifact={setArtifact}
                />
              ))}
              {live && (
                <Message message={live} onOpenArtifact={setArtifact} />
              )}
              {streaming && !live && (
                <div className="msg assistant">
                  <div className="who">C</div>
                  <div className="body">
                    <span className="typing">
                      <i /><i /><i />
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        <footer className="composer">
          <div className="composer-box">
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              onChange={autoGrow}
              onKeyDown={handleKeyDown}
              placeholder="Xabar yozing…  (Enter — yuborish, Shift+Enter — yangi qator)"
            />
            <button
              className="send"
              onClick={() => send()}
              disabled={streaming || !draft.trim()}
              aria-label="Yuborish"
            >
              ➤
            </button>
          </div>
          <div className="hint">
            <span>
              {user?.ai_in_pc
                ? "Kompyuter ruxsati yoqilgan — terminal va fayllar bilan ishlay olaman"
                : "Kompyuter ruxsati yo'q — faqat kod va tushuntirish"}
            </span>
            <span>Enter — yuborish · Shift+Enter — yangi qator</span>
          </div>
        </footer>
      </main>

      {artifact && (
        <ArtifactPanel artifact={artifact} onClose={() => setArtifact(null)} />
      )}
    </Shell>
  );
}
