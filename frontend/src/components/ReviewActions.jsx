import React, { useState } from 'react';
import { CheckCircle, RefreshCw, XCircle, Send, MessageSquare } from 'lucide-react';

export default function ReviewActions({ onDecision, isSubmitting }) {
  const [showFeedbackDrawer, setShowFeedbackDrawer] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');

  const handleApprove = () => {
    onDecision('approve');
  };

  const handleAbort = () => {
    if (window.confirm('Are you sure you want to abort this resume tailoring session?')) {
      onDecision('abort');
    }
  };

  const handleRegenerateSubmit = (e) => {
    e.preventDefault();
    if (feedbackText.trim()) {
      onDecision('regenerate', feedbackText.trim());
      setFeedbackText('');
      setShowFeedbackDrawer(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', marginTop: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h4 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', fontWeight: '700' }}>
            Human-in-the-Loop Review
          </h4>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Approve the generated resume, request AI regeneration with custom constraints, or abort session.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            type="button"
            onClick={handleApprove}
            className="btn-primary"
            disabled={isSubmitting}
            style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', boxShadow: '0 4px 15px rgba(16, 185, 129, 0.3)' }}
          >
            <CheckCircle size={18} />
            Approve Resume
          </button>

          <button
            type="button"
            onClick={() => setShowFeedbackDrawer(!showFeedbackDrawer)}
            className="btn-secondary"
            disabled={isSubmitting}
          >
            <RefreshCw size={16} />
            Regenerate with Feedback
          </button>

          <button
            type="button"
            onClick={handleAbort}
            className="btn-danger"
            disabled={isSubmitting}
          >
            <XCircle size={16} />
            Abort
          </button>
        </div>
      </div>

      {/* Expandable Feedback Drawer */}
      {showFeedbackDrawer && (
        <form onSubmit={handleRegenerateSubmit} style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: '600', color: '#a5b4fc' }}>
            <MessageSquare size={16} /> Specify Feedback for Next Rewrite Pass:
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <input
              type="text"
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              placeholder="e.g. Emphasize multi-agent Snowflake Cortex experience and shorten summary section..."
              style={{
                flex: 1,
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                color: 'var(--text-main)',
                fontFamily: 'var(--font-body)',
                fontSize: '0.9rem',
                padding: '0.65rem 1rem',
                outline: 'none'
              }}
              disabled={isSubmitting}
            />
            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting || !feedbackText.trim()}
              style={{ padding: '0.65rem 1.25rem', fontSize: '0.875rem' }}
            >
              <Send size={16} /> Submit & Regenerate
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
