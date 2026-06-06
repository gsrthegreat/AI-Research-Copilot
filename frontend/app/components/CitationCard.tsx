"use client";
import { useState } from "react";
import type { Citation } from "../lib/api";

const SOURCE_COLOR: Record<string, string> = {
  pdf: "#f97316",
  url: "#4f8ef7",
  github: "#a855f7",
  youtube: "#ef4444",
};

export default function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const color = SOURCE_COLOR[citation.source_type] ?? "#888";

  return (
    <div style={{
      background: "var(--surface-2)",
      border: "1px solid var(--border)",
      borderLeft: `3px solid ${color}`,
      borderRadius: 8,
      padding: "10px 12px",
      marginBottom: 6,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{
          background: color,
          color: "#fff",
          borderRadius: 4,
          padding: "1px 6px",
          fontSize: 11,
          fontWeight: 700,
        }}>[{index}]</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {citation.document_title}
        </span>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
          {Math.round(citation.score * 100)}%
        </span>
      </div>

      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>
        {citation.source_type.toUpperCase()}
        {citation.page_number ? ` · p.${citation.page_number}` : ""}
        {citation.source_url ? (
          <a href={citation.source_url} target="_blank" rel="noreferrer"
            style={{ color: "var(--accent)", marginLeft: 6 }}>↗ source</a>
        ) : null}
      </div>

      <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>
        {expanded ? citation.text : `${citation.text.slice(0, 120)}...`}
      </div>

      <button onClick={() => setExpanded(e => !e)} style={{
        background: "transparent",
        border: "none",
        color: "var(--accent)",
        fontSize: 11,
        cursor: "pointer",
        marginTop: 4,
        padding: 0,
      }}>
        {expanded ? "show less" : "show more"}
      </button>
    </div>
  );
}