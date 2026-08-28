import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AskSource } from '../../api/client';
import './Ask.css';

// A blank box is a hard start. Show one worked example (not editable, just a shape
// to copy) plus starters that work on any codebase.
const EXAMPLE = 'How does the inference flow work?';

const STARTERS = [
  'What does this repo do, end to end?',
  'Where does execution start, and what happens first?',
  'What are the main modules and how do they talk to each other?',
  'Where is configuration read from?',
  'How is data stored or persisted?',
  'What is the riskiest part of this codebase?',
];

// Streams the answer token-by-token from POST /api/v1/repos/:id/ask/stream (SSE).
export default function Ask() {
  const { repoId } = useParams<{ repoId: string }>();
  const [q, setQ] = useState('');
  const [asked, setAsked] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<AskSource[]>([]);
  const [needs, setNeeds] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Cancel any in-flight stream when the component unmounts — navigating to another tab or
  // switching repos otherwise leaves the fetch reader running and fires setState after
  // unmount (React warning + wasted backend work) (QA #36).
  useEffect(() => () => abortRef.current?.abort(), []);

  const ask = async (override?: string) => {
    const question = (override ?? q).trim();
    if (!repoId || !question || streaming) return;
    abortRef.current?.abort();                 // supersede any prior stream
    const ac = new AbortController();
    abortRef.current = ac;
    setQ(question); setAsked(true);
    setStreaming(true); setError(null); setAnswer(''); setSources([]); setNeeds(null); setDone(false);
    try {
      const resp = await fetch(`/api/v1/repos/${repoId}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        signal: ac.signal,
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
      if (e?.name === 'AbortError') return;   // intentional cancel (navigation) — not an error
      setError(e?.message || 'Ask failed');
    } finally {
      if (abortRef.current === ac) {
        setStreaming(false);
        abortRef.current = null;
      }
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
            placeholder="Ask anything about this codebase..."
            disabled={streaming}
            autoFocus
          />
          <button className="btn btn--primary" onClick={() => ask()} disabled={streaming || !q.trim()}>
            {streaming ? 'Asking…' : 'Ask'}
          </button>
        </div>
        {error && <div className="toast toast--err" style={{ marginTop: 12 }}>{error}</div>}
      </div>

      {!asked && (
        <div className="card">
          <div className="card-header"><h3>Not sure what to ask?</h3></div>

          <div className="ask__example" aria-hidden="true">
            <span className="ask__example-tag">example</span>
            <span className="ask__example-q">{EXAMPLE}</span>
          </div>

          <p className="ask__starters-lead">Or start with one of these - they work on any codebase:</p>
          <div className="ask__starters">
            {STARTERS.map(s => (
              <button key={s} className="ask__starter" onClick={() => ask(s)} disabled={streaming}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

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
