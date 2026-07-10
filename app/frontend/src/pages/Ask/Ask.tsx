import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AskSource } from '../../api/client';
import './Ask.css';

// Streams the answer token-by-token from POST /api/v1/repos/:id/ask/stream (SSE).
export default function Ask() {
  const { repoId } = useParams<{ repoId: string }>();
  const [q, setQ] = useState('How does the inference flow work?');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<AskSource[]>([]);
  const [needs, setNeeds] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const ask = async () => {
    if (!repoId || !q.trim() || streaming) return;
    setStreaming(true); setError(null); setAnswer(''); setSources([]); setNeeds(null); setDone(false);
    try {
      const resp = await fetch(`/api/v1/repos/${repoId}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q.trim() }),
      });
      if (!resp.ok || !resp.body) {
        let detail = 'Ask failed';
        try { detail = (await resp.json())?.detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      for (;;) {
        const { value, done: streamDone } = await reader.read();
        if (streamDone) break;
        buf += decoder.decode(value, { stream: true });
        let sep;
        while ((sep = buf.indexOf('\n\n')) !== -1) {
          const frame = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          let ev = 'message';
          let data = '';
          for (const line of frame.split('\n')) {
            if (line.startsWith('event:')) ev = line.slice(6).trim();
            else if (line.startsWith('data:')) data += line.slice(5).trim();
          }
          if (!data) continue;
          let payload: any;
          try { payload = JSON.parse(data); } catch { continue; }
          if (ev === 'sources') setSources(payload as AskSource[]);
          else if (ev === 'token') setAnswer(a => a + (payload.t || ''));
          else if (ev === 'needs_llm') setNeeds(payload.reason || 'A model is required.');
          else if (ev === 'error') setError(payload.error || 'Ask failed');
          else if (ev === 'done') setDone(true);
        }
      }
    } catch (e: any) {
      setError(e?.message || 'Ask failed');
    } finally {
      setStreaming(false);
    }
  };

  const showAnswer = answer.length > 0 || (done && !needs);

  return (
    <div>
      <div className="page-header">
        <h1>Ask the codebase</h1>
        <p>Ask anything about the indexed repo. Answers stream from your configured model, with sources cited inline.</p>
      </div>

      <div className="card">
        <div className="ask__row">
          <input
            className="input"
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !streaming) ask(); }}
            placeholder="What does this repo do? How does X work? Where is Y defined?"
            disabled={streaming}
            autoFocus
          />
          <button className="btn btn--primary" onClick={ask} disabled={streaming || !q.trim()}>
            {streaming ? 'Asking…' : 'Ask'}
          </button>
        </div>
        {error && <div className="toast toast--err" style={{ marginTop: 12 }}>{error}</div>}
      </div>

      {streaming && answer.length === 0 && !needs && (
        <div className="dash-loading">Retrieving and synthesizing…</div>
      )}

      {needs && (
        <div className="card">
          <div className="toast toast--err">
            <strong>Answers need a model.</strong> {needs}{' '}
            <Link to="/settings" style={{ color: 'var(--kyc-accent)', fontWeight: 600 }}>Open AI settings</Link>.
          </div>
        </div>
      )}

      {showAnswer && (
        <div className="card">
          <div className="card-header"><h3>Answer{streaming ? ' · streaming…' : ''}</h3></div>
          <div className="ask__answer">
            {answer}
            {streaming && <span style={{ opacity: 0.5 }}>▌</span>}
          </div>
        </div>
      )}

      {sources.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Sources ({sources.length})</h3></div>
          <div className="ask__sources">
            {sources.map((s, i) => (
              <details key={i} className="ask__source">
                <summary className="ask__source-head">
                  <span className="ask__source-file"><code>{s.file}</code>:{s.start_line}-{s.end_line}</span>
                  <span className="ask__source-name"><code>{s.name}</code></span>
                  <span className="ask__source-meta">
                    <span className={`ask__source-via ask__source-via--${s.via}`}>{s.via}</span>
                    <span className="ask__source-score">score {s.score.toFixed(3)}</span>
                  </span>
                </summary>
                <pre className="ask__source-code">{s.text}</pre>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
