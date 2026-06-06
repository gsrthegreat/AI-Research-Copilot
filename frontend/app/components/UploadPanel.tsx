"use client";
import { useRef, useState } from "react";
import { ingestPdf, ingestUrl } from "../lib/api";

export default function UploadPanel({ onSuccess }: { onSuccess: () => void }) {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleUrl() {
    if (!url.trim()) return;
    setLoading(true);
    setStatus(null);
    try {
      const res = await ingestUrl(url.trim());
      setStatus(`✅ Ingested "${res.title}" — ${res.chunk_count} chunks`);
      setUrl("");
      onSuccess();
    } catch (e: unknown) {
      setStatus(`❌ ${e instanceof Error ? e.message : "Failed"}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setStatus(null);
    try {
      const res = await ingestPdf(file);
      setStatus(`✅ Ingested "${res.title}" — ${res.chunk_count} chunks`);
      onSuccess();
    } catch (e: unknown) {
      setStatus(`❌ ${e instanceof Error ? e.message : "Failed"}`);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 10,
      padding: "14px 16px",
      marginBottom: 12,
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", marginBottom: 10 }}>
        ADD SOURCES
      </div>

      {/* URL input */}
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <input
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleUrl()}
          placeholder="Paste a URL..."
          disabled={loading}
          style={{
            flex: 1,
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "7px 10px",
            color: "var(--text)",
            fontSize: 13,
            outline: "none",
          }}
        />
        <button onClick={handleUrl} disabled={loading || !url.trim()} style={{
          padding: "7px 12px",
          background: "var(--accent)",
          color: "#fff",
          border: "none",
          borderRadius: 6,
          cursor: "pointer",
          fontSize: 13,
          opacity: loading || !url.trim() ? 0.5 : 1,
        }}>
          {loading ? "..." : "Add"}
        </button>
      </div>

      {/* PDF upload */}
      <div
        onClick={() => !loading && fileRef.current?.click()}
        style={{
          border: "1px dashed var(--border)",
          borderRadius: 6,
          padding: "12px",
          textAlign: "center",
          cursor: loading ? "not-allowed" : "pointer",
          color: "var(--text-muted)",
          fontSize: 12,
          opacity: loading ? 0.5 : 1,
        }}
      >
        📄 Drop PDF or click to upload
        <input ref={fileRef} type="file" accept=".pdf" onChange={handleFile} style={{ display: "none" }} />
      </div>

      {status && (
        <div style={{ marginTop: 8, fontSize: 12, color: status.startsWith("✅") ? "var(--success)" : "#f87171" }}>
          {status}
        </div>
      )}
    </div>
  );
}