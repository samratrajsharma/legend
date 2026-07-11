import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi, ApiRoute, DbModel } from '../../api/client';
import './ApiDb.css';

const PAGE = 10;   // long route tables are unreadable; show a window and let the user open it

export default function ApiDb() {
  const { repoId } = useParams<{ repoId: string }>();
  const [routes, setRoutes] = useState<ApiRoute[] | null>(null);
  const [models, setModels] = useState<DbModel[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [allRoutes, setAllRoutes] = useState(false);
  const [allModels, setAllModels] = useState(false);

  useEffect(() => {
    if (!repoId) return;
    setLoading(true); setError(null);
    kycApi.apiDb(repoId)
      .then(r => { setRoutes(r.data.routes || []); setModels(r.data.models || []); })
      .catch(e => setError(e?.response?.data?.detail || 'Failed to fetch API & DB data'))
      .finally(() => setLoading(false));
  }, [repoId]);

  if (loading) return <div className="dash-loading">Scanning routes & models…</div>;

  if (error) return (
    <div>
      <div className="page-header"><h1>API & DB</h1></div>
      <div className="card"><div className="toast toast--err">{error}</div></div>
    </div>
  );

  const nRoutes = routes?.length || 0;
  const nModels = models?.length || 0;
  const shownRoutes = allRoutes ? routes! : (routes || []).slice(0, PAGE);
  const shownModels = allModels ? models! : (models || []).slice(0, PAGE);

  return (
    <div>
      <div className="page-header">
        <h1>API & DB</h1>
        <p>Auto-detected HTTP routes (FastAPI, Flask, Express, etc.) and ORM models (anything with <code>__tablename__</code>).</p>
      </div>

      <div className="stats">
        <div className="stat-card">
          <div className="stat-card__label">HTTP routes</div>
          <div className="stat-card__value stat-card__value--primary">{nRoutes}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Data models</div>
          <div className="stat-card__value stat-card__value--success">{nModels}</div>
        </div>
      </div>

      {nRoutes === 0 && nModels === 0 && (
        <div className="card">
          <div className="card-header"><h3>Nothing detected</h3></div>
          <p style={{ fontSize: 13, color: 'var(--dash-text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
            This repository has no HTTP route decorators and no ORM models that KnowIT recognizes.
            That's normal for CLIs, libraries, ML training scripts, or Streamlit / desktop apps.
          </p>
          <p style={{ fontSize: 12.5, color: 'var(--dash-text-muted)', lineHeight: 1.6 }}>
            KnowIT looks for: <code>@app.get(…)</code>, <code>@app.post(…)</code>, <code>@router.put(…)</code>,
            <code>@app.route(…)</code> style decorators, and any class with a <code>__tablename__</code> attribute.
          </p>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h3>HTTP routes ({nRoutes})</h3></div>
        {nRoutes === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--dash-text-muted)' }}>— none found —</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Method</th><th>Path</th><th>File</th></tr></thead>
              <tbody>
                {shownRoutes.map((r, i) => (
                  <tr key={i}>
                    <td>
                      <span style={{
                        fontFamily: 'ui-monospace, monospace', fontSize: 11.5, fontWeight: 700,
                        padding: '2px 8px', borderRadius: 100,
                        background: methodBg(r.method), color: methodFg(r.method),
                      }}>{r.method}</span>
                    </td>
                    <td><code style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12.5 }}>{r.path}</code></td>
                    <td><code style={{ fontFamily: 'ui-monospace, monospace', fontSize: 11.5, color: 'var(--dash-text-muted)' }}>{r.file}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {nRoutes > PAGE && (
              <div className="apidb__more">
                <button className="btn btn--secondary btn--sm" onClick={() => setAllRoutes(v => !v)}>
                  {allRoutes ? `Show first ${PAGE}` : `Show all ${nRoutes} routes`}
                </button>
                {!allRoutes && <span className="apidb__more-hint">showing {PAGE} of {nRoutes}</span>}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header"><h3>Data models ({nModels})</h3></div>
        {nModels === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--dash-text-muted)' }}>— no ORM models / <code>__tablename__</code> found —</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Model</th><th>Table</th><th>File</th></tr></thead>
              <tbody>
                {shownModels.map((m, i) => (
                  <tr key={i}>
                    <td><code style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12, fontWeight: 700 }}>{m.model}</code></td>
                    <td><code style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>{m.table || '—'}</code></td>
                    <td><code style={{ fontFamily: 'ui-monospace, monospace', fontSize: 11.5, color: 'var(--dash-text-muted)' }}>{m.file}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {nModels > PAGE && (
              <div className="apidb__more">
                <button className="btn btn--secondary btn--sm" onClick={() => setAllModels(v => !v)}>
                  {allModels ? `Show first ${PAGE}` : `Show all ${nModels} models`}
                </button>
                {!allModels && <span className="apidb__more-hint">showing {PAGE} of {nModels}</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function methodBg(m: string): string {
  const c: Record<string, string> = {
    GET: 'rgba(29, 185, 84, 0.12)',
    POST: 'rgba(5, 150, 105, 0.12)',
    PUT: 'rgba(217, 119, 6, 0.12)',
    DELETE: 'rgba(220, 38, 38, 0.12)',
    PATCH: 'rgba(29, 185, 84, 0.12)',
    ANY: 'rgba(107, 114, 128, 0.12)',
  };
  return c[m.toUpperCase()] || c.ANY;
}
function methodFg(m: string): string {
  const c: Record<string, string> = {
    GET: '#1AA34A', POST: '#047857', PUT: '#b45309',
    DELETE: '#b91c1c', PATCH: '#1AA34A', ANY: '#a7a7a7',
  };
  return c[m.toUpperCase()] || c.ANY;
}
