import React, { useState } from 'react';
import { Bot, Sparkles, CheckCircle2, RotateCcw, AlertCircle } from 'lucide-react';
import { startResumeTailor, submitDecision } from './api';

import JDInput from './components/JDInput';
import ReviewPanel from './components/ReviewPanel';
import PdfPreview from './components/PdfPreview';
import ReviewActions from './components/ReviewActions';

export default function App() {
  const [appState, setAppState] = useState('idle'); // 'idle' | 'loading' | 'awaiting_review' | 'approved' | 'aborted' | 'error'
  const [sessionData, setSessionData] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleStartTailoring = async (jdText) => {
    setAppState('loading');
    setErrorMessage(null);
    try {
      const result = await startResumeTailor(jdText);
      if (result.status === 'error') {
        setErrorMessage(result.error || 'Compilation or LLM processing error');
        setAppState('error');
      } else {
        setSessionData(result);
        setAppState(result.status);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to start session');
      setAppState('error');
    }
  };

  const handleDecision = async (decision, feedback = null) => {
    if (!sessionData?.thread_id) return;

    setAppState('loading');
    setErrorMessage(null);

    try {
      const result = await submitDecision(sessionData.thread_id, decision, feedback);
      if (result.status === 'error') {
        setErrorMessage(result.error || 'Error executing decision pass');
        setAppState('error');
      } else {
        setSessionData(result);
        setAppState(result.status);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to submit decision');
      setAppState('error');
    }
  };

  const handleReset = () => {
    setAppState('idle');
    setSessionData(null);
    setErrorMessage(null);
  };

  return (
    <div>
      {/* Header Navbar */}
      <nav className="navbar">
        <div className="logo-group">
          <div style={{ background: 'var(--accent-gradient)', padding: '0.5rem', borderRadius: '12px', display: 'flex' }}>
            <Bot size={24} style={{ color: 'white' }} />
          </div>
          <div>
            <div className="logo-title">Bob the Resume Builder</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>AI Resume Tailor Agent — V1</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {sessionData && (
            <span className="badge-tag">
              Thread ID: {sessionData.thread_id.substring(0, 8)}...
            </span>
          )}
          {appState !== 'idle' && (
            <button type="button" onClick={handleReset} className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>
              <RotateCcw size={14} /> New Session
            </button>
          )}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="app-container">
        {/* Error Alert */}
        {appState === 'error' && (
          <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem', borderColor: 'rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.1)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#fca5a5', marginBottom: '0.5rem', fontWeight: '700' }}>
              <AlertCircle size={20} /> Error Processing Resume Session
            </div>
            <div style={{ fontSize: '0.9rem', color: '#fee2e2', marginBottom: '1rem', fontFamily: 'var(--font-code)' }}>
              {errorMessage}
            </div>
            <button type="button" onClick={handleReset} className="btn-secondary" style={{ fontSize: '0.85rem' }}>
              <RotateCcw size={15} /> Start New Session
            </button>
          </div>
        )}

        {/* State: Idle / Loading */}
        {(appState === 'idle' || appState === 'loading') && (
          <div style={{ maxWidth: '850px', margin: '0 auto' }}>
            <JDInput onSubmit={handleStartTailoring} isLoading={appState === 'loading'} />
          </div>
        )}

        {/* State: Awaiting Review / Approved / Aborted */}
        {(appState === 'awaiting_review' || appState === 'approved' || appState === 'aborted') && sessionData && (
          <div>
            {/* Status Banner */}
            {appState === 'approved' && (
              <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem', borderColor: 'rgba(16, 185, 129, 0.4)', background: 'rgba(16, 185, 129, 0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#6ee7b7', fontWeight: '700', fontSize: '1.1rem' }}>
                  <CheckCircle2 size={24} /> Resume Successfully Approved & Finalized!
                </div>
                <button type="button" onClick={handleReset} className="btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}>
                  Tailor Another Resume
                </button>
              </div>
            )}

            {appState === 'aborted' && (
              <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem', borderColor: 'rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ color: '#fca5a5', fontWeight: '600' }}>
                  Session was aborted. No changes were committed.
                </div>
                <button type="button" onClick={handleReset} className="btn-secondary" style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}>
                  Start New Session
                </button>
              </div>
            )}

            {/* 2-Column Review Layout */}
            <div className="grid-2col" style={{ minHeight: '650px' }}>
              <ReviewPanel
                matchResult={sessionData.match_result}
                gapReport={sessionData.gap_report}
                texDiff={sessionData.tex_diff}
              />

              <PdfPreview
                pdfUrl={sessionData.pdf_url}
                pageCount={sessionData.page_count}
                condenseAttempts={sessionData.condense_attempts}
              />
            </div>

            {/* Review Action Toolbar (Only shown when awaiting review) */}
            {appState === 'awaiting_review' && (
              <ReviewActions onDecision={handleDecision} isSubmitting={appState === 'loading'} />
            )}
          </div>
        )}
      </main>
    </div>
  );
}
