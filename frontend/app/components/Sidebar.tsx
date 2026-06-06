"use client";
import { useEffect, useState } from "react";
import { listConversations, listDocuments, type Conversation, type Document } from "../lib/api";

interface Props {
  activeConversationId?: string;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  refreshKey: number;
}

const SOURCE_ICON: Record<string, string> = {
  pdf: "📄",
  url: "🌐",
  github: "🐙",
  youtube: "▶️",
};

export default function Sidebar({ activeConversationId, onSelectConversation, onNewChat, refreshKey }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [tab, setTab] = useState<"chats" | "docs">("chats");

  useEffect(() => {
    listConversations().then(setConversations).catch(console.error);
    listDocuments().then(setDocuments).catch(console.error);
  }, [refreshKey]);

  return (
    <aside style={{
      width: 260,
      minWidth: 260,
      background: "var(--surface)",
      borderRight: "1px solid var(--border)",
      display: "flex",
      flexDirection: "column",
      height: "100vh",
    }}>
      {/* Header */}
      <div style={{ padding: "16px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 12, color: "var(--text)" }}>
          🔬 Research Copilot
        </div>
        <button onClick={onNewChat} style={{
          width: "100%",
          padding: "8px 12px",
          background: "var(--accent)",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          cursor: "pointer",
          fontSize: 13,
          fontWeight: 500,
        }}>
          + New Chat
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)" }}>
        {(["chats", "docs"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            flex: 1,
            padding: "10px",
            background: "transparent",
            border: "none",
            borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent",
            color: tab === t ? "var(--accent)" : "var(--text-muted)",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 500,
            textTransform: "capitalize",
          }}>
            {t === "chats" ? `💬 Chats (${conversations.length})` : `📚 Docs (${documents.length})`}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
        {tab === "chats" ? (
          conversations.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: 12, padding: "12px 8px" }}>
              No conversations yet
            </p>
          ) : (
            conversations.map(c => (
              <button key={c.id} onClick={() => onSelectConversation(c.id)} style={{
                width: "100%",
                textAlign: "left",
                padding: "10px 12px",
                background: activeConversationId === c.id ? "var(--surface-2)" : "transparent",
                border: "none",
                borderRadius: 8,
                cursor: "pointer",
                color: "var(--text)",
                fontSize: 13,
                marginBottom: 2,
                borderLeft: activeConversationId === c.id ? "2px solid var(--accent)" : "2px solid transparent",
              }}>
                <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {c.title}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                  {new Date(c.created_at).toLocaleDateString()}
                </div>
              </button>
            ))
          )
        ) : (
          documents.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: 12, padding: "12px 8px" }}>
              No documents ingested yet
            </p>
          ) : (
            documents.map(d => (
              <div key={d.id} style={{
                padding: "10px 12px",
                background: "var(--surface-2)",
                borderRadius: 8,
                marginBottom: 4,
              }}>
                <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {SOURCE_ICON[d.source_type] ?? "📁"} {d.title}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                  {d.chunk_count} chunks · {d.source_type}
                </div>
              </div>
            ))
          )
        )}
      </div>
    </aside>
  );
}