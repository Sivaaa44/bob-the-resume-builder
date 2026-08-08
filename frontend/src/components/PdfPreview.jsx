import React from 'react';
import { Download, FileCheck, AlertCircle, ExternalLink } from 'lucide-react';

export default function PdfPreview({ pdfUrl, pageCount, condenseAttempts }) {
  if (!pdfUrl) {
    return (
      <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
        <AlertCircle size={40} style={{ color: '#fca5a5', marginBottom: '1rem' }} />
        <h3 style={{ fontFamily: 'var(--font-heading)', color: '#fca5a5' }}>PDF Compilation Error / Pending</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.5rem', maxWidth: '400px' }}>
          The PDF compiler could not produce a preview. Please check the <strong>Gap Analysis</strong> tab or <strong>LaTeX Diff</strong> tab for detailed compile errors.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Top Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', fontWeight: '600', color: '#6ee7b7' }}>
            <FileCheck size={18} /> Tailored PDF Ready
          </span>
          <span className="badge-tag" style={{ background: pageCount === 1 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)', color: pageCount === 1 ? '#6ee7b7' : '#fca5a5' }}>
            {pageCount} Page{pageCount !== 1 ? 's' : ''} {condenseAttempts > 0 ? `(${condenseAttempts} condense pass${condenseAttempts !== 1 ? 'es' : ''})` : ''}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
            style={{ fontSize: '0.825rem', padding: '0.45rem 0.85rem' }}
          >
            <ExternalLink size={14} /> Open
          </a>
          <a
            href={pdfUrl}
            download="tailored_resume.pdf"
            className="btn-primary"
            style={{ fontSize: '0.825rem', padding: '0.45rem 0.85rem' }}
          >
            <Download size={14} /> Download PDF
          </a>
        </div>
      </div>

      {/* PDF Iframe */}
      <div style={{ flex: 1, minHeight: '600px', borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--border-color)', background: '#1e293b' }}>
        <iframe
          src={`${pdfUrl}#toolbar=0&navpanes=0&scrollbar=0`}
          title="Resume PDF Preview"
          width="100%"
          height="100%"
          style={{ border: 'none', display: 'block' }}
        />
      </div>
    </div>
  );
}
