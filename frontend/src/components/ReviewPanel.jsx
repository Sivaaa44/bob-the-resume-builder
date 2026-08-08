import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, FileCode, Layers, ArrowRight } from 'lucide-react';

export default function ReviewPanel({ matchResult, gapReport, texDiff }) {
  const [activeTab, setActiveTab] = useState('skills'); // 'skills' | 'gap' | 'diff'

  const matched = matchResult?.matched || [];
  const partial = matchResult?.partial || [];
  const missing = matchResult?.missing || [];

  const diffLines = texDiff ? texDiff.split('\n') : [];

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem', marginBottom: '1.25rem' }}>
        <button
          className={`btn-secondary ${activeTab === 'skills' ? 'active-tab' : ''}`}
          onClick={() => setActiveTab('skills')}
          style={{
            fontSize: '0.875rem',
            padding: '0.5rem 1rem',
            background: activeTab === 'skills' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
            borderColor: activeTab === 'skills' ? 'var(--accent-primary)' : 'transparent',
            color: activeTab === 'skills' ? '#a5b4fc' : 'var(--text-muted)'
          }}
        >
          <Layers size={16} /> Skill Matrix ({matched.length + partial.length + missing.length})
        </button>

        <button
          className={`btn-secondary ${activeTab === 'gap' ? 'active-tab' : ''}`}
          onClick={() => setActiveTab('gap')}
          style={{
            fontSize: '0.875rem',
            padding: '0.5rem 1rem',
            background: activeTab === 'gap' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
            borderColor: activeTab === 'gap' ? 'var(--accent-primary)' : 'transparent',
            color: activeTab === 'gap' ? '#a5b4fc' : 'var(--text-muted)'
          }}
        >
          <AlertTriangle size={16} /> Gap Analysis
        </button>

        <button
          className={`btn-secondary ${activeTab === 'diff' ? 'active-tab' : ''}`}
          onClick={() => setActiveTab('diff')}
          style={{
            fontSize: '0.875rem',
            padding: '0.5rem 1rem',
            background: activeTab === 'diff' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
            borderColor: activeTab === 'diff' ? 'var(--accent-primary)' : 'transparent',
            color: activeTab === 'diff' ? '#a5b4fc' : 'var(--text-muted)'
          }}
        >
          <FileCode size={16} /> LaTeX Diff
        </button>
      </div>

      {/* Tab Content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {activeTab === 'skills' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Matched */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', color: '#6ee7b7', fontSize: '0.9rem', fontWeight: '600' }}>
                <CheckCircle2 size={18} /> Direct Ground-Truth Matches ({matched.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {matched.length > 0 ? (
                  matched.map((skill, i) => (
                    <span key={i} className="skill-pill skill-matched">
                      {skill}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>None</span>
                )}
              </div>
            </div>

            {/* Partial */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', color: '#fcd34d', fontSize: '0.9rem', fontWeight: '600' }}>
                <AlertTriangle size={18} /> Adjacent / Reframeable Skills ({partial.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {partial.length > 0 ? (
                  partial.map((skill, i) => (
                    <span key={i} className="skill-pill skill-partial">
                      {skill}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>None</span>
                )}
              </div>
            </div>

            {/* Missing */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', color: '#fca5a5', fontSize: '0.9rem', fontWeight: '600' }}>
                <XCircle size={18} /> Missing Gaps ({missing.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {missing.length > 0 ? (
                  missing.map((skill, i) => (
                    <span key={i} className="skill-pill skill-missing">
                      {skill}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No gaps detected!</span>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'gap' && (
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6', fontSize: '0.9rem', color: '#e2e8f0' }}>
            {gapReport ? (
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                {gapReport}
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>
                No gap analysis available.
              </div>
            )}
          </div>
        )}

        {activeTab === 'diff' && (
          <div className="diff-container">
            {diffLines.length > 0 ? (
              diffLines.map((line, idx) => {
                let lineClass = '';
                if (line.startsWith('+') && !line.startsWith('+++')) lineClass = 'diff-line-add';
                else if (line.startsWith('-') && !line.startsWith('---')) lineClass = 'diff-line-del';
                else if (line.startsWith('@@')) lineClass = 'diff-line-info';

                return (
                  <span key={idx} className={lineClass}>
                    {line}
                  </span>
                );
              })
            ) : (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1.5rem' }}>
                No LaTeX changes detected in this run.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
