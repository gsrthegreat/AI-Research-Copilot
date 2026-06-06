"use client";
import { useEffect, useRef } from "react";
import CitationCard from "./CitationCard";
import type { Message } from "../lib/api";

export default function ChatThread({ messages }: { messages: Message[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--text-muted)",
        gap: 8,
      }}>
        <div style={{ fontSize: 32 }}>🔬</div>
        <div style={{ fontSize: 15, fontWeight: 500 }}>Ask anything about your documents</div>
        <div style={{ fontSize: 13 }}>Upload a PDF or URL to get started</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "20px 0" }}>
      {messages.map((msg, i) => (
        <div key={msg.id ?? i} style={{
          padding: "8px 24px",
          marginBottom: 4,
        }}>
          {msg.role === "user" ? (
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <div style={{
                background: "var(--accent)",
                color: "#fff",
                padding: "10px 16px",
                borderRadius: "16px 16px 4px 16px",
                maxWidth: "70%",
                fontSize: 14,
                lineHeight: 1.6,
              }}>
                {msg.content}
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <div style={{
                width: 28,
                height: 28,
                background: "var(--surface-2)",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
                flexShrink: 0,
                marginTop: 2,
              }}>🔬</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  padding: "12px 16px",
                  borderRadius: "4px 16px 16px 16px",
                  fontSize: 14,
                  lineHeight: 1.7,
                  color: "var(--text)",
                  whiteSpace: "pre-wrap",
                }}>
                  {msg.content}
                </div>
                {msg.citations && msg.citations.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600 }}>
                      SOURCES ({msg.citations.length})
                    </div>
                    {msg.citations.map((c, ci) => (
                      <CitationCard key={c.chunk_id} citation={c} index={ci + 1} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}   