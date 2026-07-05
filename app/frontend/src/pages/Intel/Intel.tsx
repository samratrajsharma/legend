import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi } from '../../api/client';
import './Intel.css';

type Tab = 'techdebt' | 'memory' | 'impact' | 'coverage';

export default function Intel() {
  const { repoId } = useParams<{ repoId: string }>();
  const [tab, setTab] = useState<Tab>('techdebt');

  return (
    <div>
      <div className="page-header">
        <h1>Intel</h1>
        <p>Tech debt, engineering memory (decisions/errors/notes), impact analysis, and test coverage.</p>
      </div>

      <div className="card intel__tabs">
        {(['techdebt','memory','impact','coverage'] as Tab[]).map(t => (
          <button key={t} className={`intel__tab${tab===t?' intel__tab--active':''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {repoId && tab === 'techdebt' && <TechDebt rid={repoId} />}
      {repoId && tab === 'memory'   && <Memory rid={repoId} />}
      {repoId && tab === 'impact'   && <Impact rid={repoId} />}
      {repoId && tab === 'coverage' && <Coverage rid={repoId} />}
    </div>
  );
}

function TechDebt({ rid }: { rid: string }) {
  const [d, setD] = useState<any>(null);
  useEffect(() => { kycApi.intelTechdebt(rid).then(r => setD(r.data)); }, [rid]);
  if (!d) return <div className="dash-loading">Analyzing…</div>;
  return (
    <>
      <div className="stats">
        <div className="stat-card"><div className="stat-card__label">Dead code</div><div className="stat-card__value stat-card__value--danger">{d.dead_code.length}</div></div>
        <div className="stat-card"><div className="stat-card__label">Hotspots</div><div className="stat-card__value stat-card__value--warning">{d.complexity_hotspots.length}</div></div>
        <div className="stat-card"><div className="stat-card__label">Duplicates</div><div className="stat-card__value">{d.near_duplicates.length}</div></div>
        <div className="stat-card"><div className="stat-card__label">Import cycles</div><div className="stat-card__value">{d.import_cycles.length}</div></div>
        <div className="stat-card"><div className="stat-card__label">God files</div><div className="stat-card__value">{d.god_files.length}</div></div>
        <div className="stat-card"><div className="stat-card__label">Undocumented</div><div className="stat-card__value">{d.undocumented.length}</div></div>
      </div>

      <TableSection title="Dead code" rows={d.dead_code} cols={['symbol','file']} />
      <TableSection title="Complexity hotspots" rows={d.complexity_hotspots} cols={['symbol','file','complexity']} />
      <TableSection title="God files" rows={d.god_files} cols={['file','symbols','complexity']} />
      <TableSection title="Undocumented symbols" rows={d.undocumented.slice(0, 50)} cols={['symbol','file','kind']} />

      {d.import_cycles.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Import cycles ({d.import_cycles.length})</h3></div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {d.import_cycles.map((c: string[], i: number) => (
              <li key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--dash-border)', fontSize: 12.5 }}>
                {c.map((f, j) => <span key={j}><code style={{ fontFamily: 'ui-monospace' }}>{f}</code>{j < c.length - 1 ? ' ↔ ' : ''}</span>)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {d.near_duplicates.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Near-duplicate pairs ({d.near_duplicates.length})</h3></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Symbol A</th><th>Symbol B</th><th>Similarity</th></tr></thead>
              <tbody>
                {d.near_duplicates.slice(0, 30).map((p: any, i: number) => (
                  <tr key={i}>
                    <td><code>{p.a}</code></td>
                    <td><code>{p.b}</code></td>
                    <td>{Math.round(p.similarity * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function TableSection({ title, rows, cols }: { title: string; rows: any[]; cols: string[] }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="card">
      <div className="card-header"><h3>{title} ({rows.length})</h3></div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map(c => <td key={c}><code style={{ fontFamily: 'ui-monospace', fontSize: 12 }}>{String(r[c] ?? '')}</code></td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Memory({ rid }: { rid: string }) {
  const [data, setData] = useState<any>(null);
  const [kind, setKind] = useState<'decisions'|'errors'|'memory'>('decisions');
  const [title, setTitle] = useState(''); const [body, setBody] = useState('');
  const refresh = () => kycApi.intelMemory(rid).then(r => setData(r.data));
  useEffect(() => { refresh(); }, [rid]);
  const add = async () => {
    if (!title.trim()) return;
    await kycApi.intelMemoryAdd(rid, kind, title, body);
    setTitle(''); setBody(''); refresh();
  };
  const del = async (k: string, eid: string) => { await kycApi.intelMemoryDel(rid, k, eid); refresh(); };
  if (!data) return <div className="dash-loading">Loading…</div>;
  return (
    <>
      <div className="card">
        <div className="card-header"><h3>Add an entry</h3></div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          {(['decisions','errors','memory'] as const).map(k => (
            <button key={k} className={`learn__pill${kind===k?' learn__pill--active':''}`} onClick={() => setKind(k)}>{k}</button>
          ))}
        </div>
        <input className="input" placeholder="Title" value={title} onChange={e => setTitle(e.target.value)} style={{ marginBottom: 8 }} />
        <textarea className="input" placeholder="Body (optional)" value={body} onChange={e => setBody(e.target.value)} rows={3} style={{ marginBottom: 8, fontFamily: 'inherit' }} />
        <button className="btn btn--primary" onClick={add} disabled={!title.trim()}>Add to {kind}</button>
      </div>

      {(['decisions','errors','memory'] as const).map(k => (
        <div key={k} className="card">
          <div className="card-header"><h3 style={{ textTransform: 'capitalize' }}>{k} ({data[k].length})</h3></div>
          {data[k].length === 0 ? <p style={{ fontSize: 13, color: 'var(--dash-text-muted)' }}>— none —</p> : (
            <div className="intel__entries">
              {data[k].map((e: any) => (
                <div key={e.id} className="intel__entry">
                  <div className="intel__entry-head">
                    <strong>{e.title}</strong>
                    <span className="intel__entry-meta">{e.date}</span>
                    <button className="btn btn--secondary btn--sm" onClick={() => del(k, e.id)}>Delete</button>
                  </div>
                  {e.body && <div className="intel__entry-body">{e.body}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </>
  );
}

function Impact({ rid }: { rid: string }) {
  const [symbol, setSymbol] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [nodes, setNodes] = useState<string[]>([]);
  useEffect(() => { kycApi.graphNodes(rid).then(r => setNodes(r.data.nodes.filter(n => n.includes('::')))); }, [rid]);
  const run = async () => {
    if (!symbol) return;
    setLoading(true);
    try { const r = await kycApi.intelImpact(rid, symbol); setResult(r.data); }
    finally { setLoading(false); }
  };
  return (
    <div className="card">
      <div className="card-header"><h3>Impact of a symbol</h3></div>
      <div style={{ display: 'flex', gap: 10 }}>
        <select className="input" value={symbol} onChange={e => setSymbol(e.target.value)}>
          <option value="">(pick a symbol)</option>
          {nodes.map(n => <option key={n} value={n}>{n}</option>)}
        </select>
        <button className="btn btn--primary" onClick={run} disabled={!symbol || loading}>Analyze</button>
      </div>
      {loading && <div className="dash-loading" style={{ minHeight: 100 }}>Analyzing…</div>}
      {result && (
        <pre className="track__changelog" style={{ marginTop: 14 }}>{JSON.stringify(result, null, 2)}</pre>
      )}
    </div>
  );
}

function Coverage({ rid }: { rid: string }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => { kycApi.intelCoverage(rid).then(r => setData(r.data)).catch(() => setData({})); }, [rid]);
  if (!data) return <div className="dash-loading">Loading…</div>;
  return (
    <div className="card">
      <div className="card-header"><h3>Test-reference coverage</h3></div>
      <pre className="track__changelog">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
