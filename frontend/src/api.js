export async function startResumeTailor(jdText) {
  const response = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd_text: jdText }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Server error' }));
    throw new Error(errorData.detail || `Server returned status ${response.status}`);
  }

  return response.json();
}

export async function submitDecision(threadId, decision, feedback = null) {
  const response = await fetch('/api/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      decision: decision,
      feedback: feedback
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Server error' }));
    throw new Error(errorData.detail || `Server returned status ${response.status}`);
  }

  return response.json();
}
