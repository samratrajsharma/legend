import { useEffect, useRef, useState } from 'react';
import { kycApi, QASource, FileNode } from '../../api/kycApi';
import './QAChatPanel.css';

interface Msg { role: 'user' | 'assistant'; text: string; sources?: QASource[]; }

export default function QAChatPanel({ repoId, ready }: { repoId: string; ready?: boolean }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<string | undefined>();
  const [fileMap, setFileMap] = useState<Record<string, string>>({});
  const [drawer, setDrawer] = useState<{ path: string; content: string; range: [number, number] } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    kycApi.listFiles(repoId).then((r) => {
      const m: Record<string, string> = {};
      r.data.forEach((f: FileNode) => { m[f.path] = f.id; });
      setFileMap(m);
    }).catch(() => {});
  }, [repoId]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  const ask = async () => {
    const question = q.trim();
    if (!question || busy) return;
    setMsgs((m) => [...m, { role: 'user', text: question }]);
    setQ(''); setBusy(true);
    try {
      const r = await kycApi.askQuestion(repoId, question, session);
      setSession(r.data.session_id);
      setMsgs((m) => [...m, { role: 'assistant', text: r.data.answer, sources: r.data.sources }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: 'assistant', text: e?.response?.data?.detail || 'Something went wrong.' }]);
    } finally { setBusy(false); }
  };

  const openSource = async (s: QASource) => {
    const fid = fileMap[s.path];
    if (!fid) return;
    try {
      const r = await kycApi.fileContent(repoId, fid);
      setDrawer({ path: s.path, content: r.data.content, range: [s.line_start, s.line_end] });
    } catch { /* ignore */ }
  };

  if (ready === false) {
    return <div className="card"><div className="empty-state"><h3>Still indexing</h3>
      <p>Q&amp;A becomes available once indexing finishes.</p></div></div>;
  }

  return (
    <div className={'kyc-qa' + (drawer ? ' kyc-qa--drawer' : '')}>
      <div className="card kyc-qa-main">
        <div className="kyc-qa-msgs">
          {msgs.length === 0 && (
            <div className="empty-state"><p>Ask a question about this codebase — e.g. “Where does request authentication happen?”</p></div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={'kyc-msg kyc-msg--' + m.role}>
              <div className="kyc-msg-body">{m.text}</div>
              {m.sources && m.sources.length > 0 && (
                <div className="kyc-msg-src">
                  {m.sources.map((s, j) => (
                    <button key={j} className="chip kyc-src-chip" onClick={() => openSource(s)}>
                      {s.path}:{s.line_start}-{s.line_end}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {busy && <div className="kyc-msg kyc-msg--assistant"><div className="kyc-msg-body"><orc-spinner size="sm" /> Thinking…</div></div>}
          <div ref={endRef} />
        </div>
        <div className="kyc-qa-input">
          <input value={q} placeholder="Ask about this codebase…" disabled={busy}
            onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') ask(); }} />
          <button className="btn btn--primary" disabled={busy || !q.trim()} onClick={ask}>Ask</button>
        </div>
      </div>

      {drawer && (
        <div className="card kyc-qa-side">
          <div className="card-header"><h3>{drawer.path}</h3>
            <button className="btn btn--secondary btn--sm" onClick={() => setDrawer(null)}>Close</button></div>
          <pre className="kyc-srcview">
            {drawer.content.split('\n').map((ln, i) => {
              const n = i + 1;
              const hit = n >= drawer.range[0] && n <= drawer.range[1];
              return (
                <div key={i} className={'kyc-srcline' + (hit ? ' kyc-srcline--hit' : '')}>
                  <span className="kyc-srcnum">{n}</span>{ln || ' '}
                </div>
              );
            })}
          </pre>
        </div>
      )}
    </div>
  );
}
