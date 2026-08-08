import React, { useState } from 'react';
import { Sparkles, FileText, Loader2, Play } from 'lucide-react';

const SAMPLE_JD = `We are seeking a Software Development / AI Engineer to join our team.

Responsibilities:
- Build multi-agent AI systems, NLP-to-SQL pipelines, and RAG architectures for enterprise applications.
- Develop high-performance backend microservices using Python, FastAPI, and relational databases (SQLite / PostgreSQL).
- Implement real-time WebSockets / WebRTC communications and tool-calling interfaces (MCP).
- Experience with Groq API, Snowflake Cortex, Pinecone DB, and Automation Anywhere is a major plus.

Requirements:
- Strong experience in Python, JavaScript/TypeScript, and React.js.
- Background in software engineering and AI agent development.
- Knowledge of Docker, Kubernetes, and GCP is preferred.`;

export default function JDInput({ onSubmit, isLoading }) {
  const [jdText, setJdText] = useState('');

  const handleLoadSample = () => {
    setJdText(SAMPLE_JD.trim());
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (jdText.strip ? jdText.strip() : jdText.trim()) {
      onSubmit(jdText.trim());
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.35rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText style={{ color: 'var(--accent-primary)' }} size={22} />
            Target Job Description (JD)
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Paste the raw job description to tailor your resume against your ground-truth background.
          </p>
        </div>
        <button
          type="button"
          onClick={handleLoadSample}
          className="btn-secondary"
          style={{ fontSize: '0.825rem', padding: '0.5rem 0.9rem' }}
          disabled={isLoading}
        >
          <Sparkles size={15} style={{ color: '#f59e0b' }} />
          Load Sample JD
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <textarea
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          placeholder="Paste Job Description text here..."
          rows={14}
          style={{
            width: '100%',
            background: 'rgba(15, 23, 42, 0.7)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            color: 'var(--text-main)',
            fontFamily: 'var(--font-body)',
            fontSize: '0.95rem',
            padding: '1rem',
            resize: 'vertical',
            outline: 'none',
            lineHeight: '1.6'
          }}
          disabled={isLoading}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.25rem' }}>
          <span style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
            {jdText.length} characters
          </span>
          <button
            type="submit"
            className="btn-primary"
            disabled={isLoading || !jdText.trim()}
          >
            {isLoading ? (
              <>
                <Loader2 size={18} className="spin-icon" />
                Analyzing & Tailoring...
              </>
            ) : (
              <>
                <Play size={18} />
                Tailor Resume
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
