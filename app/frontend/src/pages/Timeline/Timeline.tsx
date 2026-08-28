import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { kycApi, TimelineEvent, TimelineMetrics } from '../../api/client';
import './Timeline.css';

const METRICS: [keyof TimelineMetrics, string][] = [
  ['files', 'Files'], ['symbols', 'Symbols'], ['loc', 'LOC'],
  ['avg_complexity', 'Avg complexity'], ['dead_code', 'Dead code'],
];

export default function Timeline() {
  const { repoId } = useParams<{ repoId: string }>();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [series, setSeries] = useState<(TimelineMetrics & { ts: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [capturing, setCapturing] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [narr, setNarr] = useState<Record<string, { loading?: boolean; text?: string; needs?: boolean; reason?: string }>>({});
  const [auto, setAuto] = useState(false);

  const load = useCallback(() => {
    if (!repoId) return;
    setLoading(true); setErr(null);
    Promise.all([kycApi.trackTimeline(repoId), kycApi.trackTrends(repoId)])
      .then(([t, tr]) => { setEvents(t.data.events || []); setSeries(tr.data.series || []); })
      // a real load failure must show an error, not the misleading "no history yet" empty state
      .catch((e: { response?: { data?: { detail?: string } } }) =>
        setErr(e?.response?.data?.detail || 'Failed to load the timeline.'))
      .finally(() => setLoading(false));
  }, [repoId]);
  useEffect(() => {
    if (!repoId) return;
    // Pull any new git commits (deduped), then load the timeline.
    kycApi.trackImportGit(repoId).catch(() => {}).finally(() => load());
  }, [repoId, load]);

  // Auto-capture: while on, cheaply poll for changes and capture when dirty.
  useEffect(() => {
    if (!auto || !repoId) return;
    const iv = setInterval(() => {
      kycApi.trackDirty(repoId).then(d => {
        if (d.data.dirty) kycApi.trackCapture(repoId).then(() => load()).catch(() => {});
      }).catch(() => {});
    }, 8000);
    return () => clearInterval(iv);
  }, [auto, repoId, load]);

  const capture = () => {
    if (!repoId) return;
    setCapturing(true); setMsg('');
    kycApi.trackCapture(repoId).then(r => {
      if (r.data.baseline) setMsg('Baseline captured — future captures will show what changed since now.');
      else if (r.data.changed) setMsg('Captured — ' + (r.data.event?.summary || 'changes recorded') + '.');
      else setMsg('No structural changes since the last capture.');
      load();
    }).catch((e: { response?: { data?: { detail?: string } }; message?: string }) =>
      setMsg('Capture failed: ' + (e?.response?.data?.detail || e?.message || 'error')))
      .finally(() => setCapturing(false));
  };

  const narrate = (ts: string) => {
    if (!repoId) return;
    setNarr(n => ({ ...n, [ts]: { loading: true } }));
    kycApi.trackNarrate(repoId, ts).then(r => {
      if (r.data.needs_llm) setNarr(n => ({ ...n, [ts]: { needs: true, reason: r.data.reason || 'Connect a model.' } }));
      else setNarr(n => ({ ...n, [ts]: { text: r.data.narration || '' } }));
    }).catch((e: { response?: { data?: { detail?: string } } }) =>
      setNarr(n => ({ ...n, [ts]: { text: 'Narration failed: ' + (e?.response?.data?.detail || 'error') } })));
  };

  const importGit = () => {
    if (!repoId) return;
    kycApi.trackImportGit(repoId).then(r => {
      setMsg(r.data.is_git ? `Imported ${r.data.imported} commit(s) from git history.` : 'Not a git repo — nothing to import.');
      load();
    }).catch(() => setMsg('Git import failed.'));
  };

  const latest = series.length ? series[series.length - 1] : null;
  const first = series.length ? series[0] : null;
  const deltaSinceFirst = (k: keyof TimelineMetrics) =>
    latest && first ? Math.round((Number(latest[k]) - Number(first[k])) * 100) / 100 : 0;
  const fmt = (n: number) => (n > 0 ? `+${n}` : `${n}`);

  return (
    <div>
      <div className="page-header">
        <h1>Timeline</h1>
        <p>What has changed in this folder over time. Each capture re-scans it and records the difference since the last one — no LLM needed.</p>
      </div>

      <div className="card tl-capturebar">
        <div>
          <div className="tl-capturebar__title">Capture the current state</div>
          <div className="tl-capturebar__sub">
            {series.length} capture{series.length === 1 ? '' : 's'} recorded
            {latest ? ` · last: ${new Date(latest.ts).toLocaleString()}` : ''}
          </div>
        </div>
        <div className="tl-capturebar__actions">
          <label className="tl-auto" title="While on, watches this folder and captures when it changes (this tab only)">
            <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} /> Auto-capture
          </label>
          <button className="btn btn--secondary btn--sm" onClick={importGit}>Import git history</button>
          <button className="btn btn--primary" onClick={capture} disabled={capturing}>
            {capturing ? 'Scanning…' : 'Capture now'}
          </button>
        </div>
      </div>
      {msg && (
        <div
          className={`toast ${/fail|error|could not|denied|timed out/i.test(msg) ? 'toast--err' : 'toast--ok'}`}
          style={{ marginBottom: 16 }}
        >
          {msg}
        </div>
      )}

      {latest && (
        <div className="stats">
          {METRICS.map(([k, label]) => {
            const d = deltaSinceFirst(k);
            return (
              <div key={k} className="stat-card">
                <div className="stat-card__label">{label}</div>
                <div className="stat-card__value">{latest[k]}</div>
                {series.length > 1 && <div className="tl-trend">{fmt(d)} since first</div>}
              </div>
            );
          })}
        </div>
      )}

      {loading ? (
        <div className="dash-loading">Loading timeline…</div>
      ) : err ? (
        <div className="toast toast--err">{err} <button className="btn btn--ghost" onClick={load}>Retry</button></div>
      ) : events.length === 0 ? (
        <div className="empty-state">
          <h3>No history yet</h3>
          <p>Click “Capture now” to record the baseline. After you (or your AI tool) change the folder, capture again to see exactly what moved.</p>
        </div>
      ) : (
        <div className="tl-list">
          {events.map((e, i) => (
            <div key={i} className={`tl-item tl-item--${e.kind}`}>
              <div className="tl-item__head">
                <span className="tl-item__dot" />
                <span className="tl-item__summary">{e.summary}</span>
                <span className="tl-item__time">{new Date(e.ts).toLocaleString()}</span>
              </div>
              {e.kind === 'commit' && (e.author || e.sha) && (
                <div className="tl-item__commitmeta">{e.author}{e.sha ? ` · ${e.sha}` : ''}</div>
              )}
              {e.kind !== 'baseline' && (
                <>
                  <div className="tl-item__narrate">
                    {narr[e.ts]?.text ? (
                      <div className="tl-narration">{narr[e.ts]?.text}</div>
                    ) : narr[e.ts]?.needs ? (
                      <div className="tl-narration tl-narration--muted">
                        {narr[e.ts]?.reason}{' '}
                        <Link to="/settings" style={{ color: 'var(--kyc-accent)', fontWeight: 600 }}>AI settings</Link>
                      </div>
                    ) : (
                      <button className="btn btn--secondary btn--sm" disabled={narr[e.ts]?.loading}
                        onClick={() => narrate(e.ts)}>
                        {narr[e.ts]?.loading ? 'Explaining…' : 'Explain this change'}
                      </button>
                    )}
                  </div>
                  <details className="tl-item__details">
                  <summary>Details</summary>
                  <div className="tl-detail-grid">
                    {!!e.files_added?.length && <TLBlock title={`Files added (${e.files_added.length})`} items={e.files_added} />}
                    {!!e.files_removed?.length && <TLBlock title={`Files removed (${e.files_removed.length})`} items={e.files_removed} />}
                    {!!e.files_modified?.length && <TLBlock title={`Files modified (${e.files_modified.length})`} items={e.files_modified.map(f => f.loc != null || f.cx_total != null ? `${f.file}  (LOC ${f.loc_was ?? '?'}\u2192${f.loc ?? '?'}, cx ${f.cx_was ?? '?'}\u2192${f.cx_total ?? '?'})` : f.file)} />}
                    {!!e.symbols_added?.length && <TLBlock title={`Symbols added (${e.symbols_added.length})`} items={e.symbols_added.map(s => `${s.symbol}  (${s.kind ?? '?'}, cx ${s.cx ?? 0}) — ${s.file}`)} />}
                    {!!e.symbols_changed?.length && <TLBlock title={`Symbols changed (${e.symbols_changed.length})`} items={e.symbols_changed.map(s => `${s.symbol}  (cx ${s.cx_was ?? 0}→${s.cx ?? 0}) — ${s.file}`)} />}
                    {!!e.symbols_removed?.length && <TLBlock title={`Symbols removed (${e.symbols_removed.length})`} items={e.symbols_removed.map(s => `${s.symbol} — ${s.file}`)} />}
                    {!(e.files_added?.length || e.files_removed?.length || e.files_modified?.length || e.symbols_added?.length || e.symbols_changed?.length || e.symbols_removed?.length) && (
                      <div className="tl-block"><div className="tl-block__title" style={{ color: 'var(--dash-text-muted)', fontWeight: 400 }}>No file-level changes recorded for this commit.</div></div>
                    )}
                  </div>
                </details>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TLBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="tl-block">
      <div className="tl-block__title">{title}</div>
      <ul className="tl-block__list">
        {items.slice(0, 50).map((it, i) => <li key={i}>{it}</li>)}
      </ul>
    </div>
  );
}
