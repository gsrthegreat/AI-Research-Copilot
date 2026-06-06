"use client";
import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatThread from "./components/ChatThread";
import UploadPanel from "./components/UploadPanel";
import { sendChat, getConversation, type Message } from "./lib/api";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [showUpload, setShowUpload] = useState(false);

  const refresh = useCallback(() => setSidebarRefresh(n => n + 1), []);

  async function handleSelectConversation(id: string) {
    try {
      const conv = await getConversation(id);
      setConversationId(id);
      setMessages(conv.messages ?? []);
      setError(null);
    } catch {
      setError("Failed to load conversation");
    }
  }

  function handleNewChat() {
    setConversationId(undefined);
    setMessages([]);
    setError(null);
    setInput("");
  }

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: q,
    };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await sendChat(q, conversationId);
      const assistantMsg: Message = {
        id: res.message_id,
        role: "assistant",
        content: res.answer,
        citations: res.citations,
      };
      setConversationId(res.conversation_id);
      setMessages(prev => [...prev, assistantMsg]);
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setMessages(prev => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        refreshKey={sidebarRefresh}
      />

      {/* Main */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

        {/* Topbar */}
        <div style={{
          height: 52,
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          padding: "0 20px",
          gap: 12,
          background: "var(--surface)",
          flexShrink: 0,
        }}>
          <span style={{ flex: 1, fontSize: 14, color: "var(--text-muted)" }}>
            {conversationId ? `Conversation` : "New conversation"}
          </span>
          <button onClick={() => setShowUpload(v => !v)} style={{
            padding: "6px 14px",
            background: showUpload ? "var(--surface-2)" : "transparent",
            border: "1px solid var(--border)",
            borderRadius: 6,
            color: "var(--text)",
            cursor: "pointer",
            fontSize: 13,
          }}>
            {showUpload ? "✕ Close" : "＋ Add Source"}
          </button>
        </div>

        {/* Upload panel */}
        {showUpload && (
          <div style={{ padding: "12px 20px 0", flexShrink: 0 }}>
            <UploadPanel onSuccess={() => { refresh(); setShowUpload(false); }} />
          </div>
        )}

        {/* Chat */}
        <ChatThread messages={messages} />

        {/* Error */}
        {error && (
          <div style={{
            margin: "0 20px 8px",
            padding: "10px 14px",
            background: "#450a0a",
            border: "1px solid #7f1d1d",
            borderRadius: 8,
            fontSize: 13,
            color: "#fca5a5",
          }}>
            ⚠️ {error}
          </div>
        )}

        {/* Input */}
        <div style={{
          padding: "12px 20px 16px",
          borderTop: "1px solid var(--border)",
          background: "var(--surface)",
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 8 }}>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask a question about your documents... (Enter to send)"
              rows={2}
              disabled={loading}
              style={{
                flex: 1,
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "10px 14px",
                color: "var(--text)",
                fontSize: 14,
                resize: "none",
                outline: "none",
                fontFamily: "inherit",
                lineHeight: 1.5,
              }}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              style={{
                padding: "0 20px",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: 10,
                cursor: "pointer",
                fontSize: 20,
                opacity: loading || !input.trim() ? 0.4 : 1,
                flexShrink: 0,
              }}
            >
              {loading ? "⏳" : "↑"}
            </button>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
            Shift+Enter for new line · Enter to send
          </div>
        </div>
      </div>
    </div>
  );
}