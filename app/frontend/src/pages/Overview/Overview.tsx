import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { kycApi, OverviewResponse } from '../../api/client';
import './Overview.css';
import InfoTip from '../../components/InfoTip/InfoTip';
import { gdef } from '../../lib/glossary';

export default function Overview() {
  const { repoId } = useParams<{ repoId: string }>();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!repoId) return;
    setData(null); setError(null);
    kycApi.overview(repoId)
      .then(r => setData(r.data))
      .catch(e => setError(e?.response?.data?.detail || 'Failed to load overview'));
  }, [repoId]);

  if (error) {
    return (
      <div>
        <div className="page-header"><h1>Overview</h1></div>
        <div className="card"><div className="toast toast--err">{error}</div></div>
      </div>
    );
  }

  if (!data) return <div className="dash-loading">Loading overview…</div>;

  const { stats, insights, languages } = data;

  return (
    <div>
      <div className="page-header">
        <h1>Overview</h1>
        <p>{stats.repo} · commit <code>{stats.commit}</code> · retrieval {stats.retriever}</p>
      </div>

      <div className="stats">
        <div className="stat-card">
          <div className="stat-card__label">Code files</div>
          <div className="stat-card__value stat-card__value--primary">{stats.python_files}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Symbols<InfoTip label="Symbols" text={gdef('Symbol')} /></div>
          <div className="stat-card__value">{stats.symbols}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Graph edges<InfoTip label="Graph edges" text={gdef('Graph edges')} /></div>
          <div className="stat-card__value">{stats.graph_edges}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Chunks<InfoTip label="Chunks" text={gdef('Chunks')} /></div>
          <div className="stat-card__value">{stats.chunks}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Total LOC<InfoTip label="Total LOC" text={gdef('LOC')} /></div>
          <div className="stat-card__value stat-card__value--success">{insights.loc_total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Avg complexity / fn<InfoTip label="Avg complexity / fn" text={gdef('Avg complexity / fn')} /></div>
          <div className="stat-card__value stat-card__value--warning">{insights.avg_complexity}</div>
        </div>
      </div>

      <div className="ov-row">
        <div className="card">
          <div className="card-header"><h3>Languages</h3></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Language</th><th>Files</th><th>LOC</th><th>Symbols</th></tr></thead>
              <tbody>
                {languages.map(l => (
                  <tr key={l.language}>
                    <td>{l.language}</td>
                    <td>{l.files}</td>
                    <td>{l.loc}</td>
                    <td>{l.symbols}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h3>Entry points<InfoTip label="Entry points" text={gdef('Entry points')} /></h3></div>
          {insights.entry_files.length === 0 ? (
            <p className="ov-muted">— none detected —</p>
          ) : (
            <ul className="ov-list">
              {insights.entry_files.map(f => <li key={f}><code>{f}</code></li>)}
            </ul>
          )}
        </div>
      </div>

      <div className="ov-row">
        <div className="card">
          <div className="card-header"><h3>Hub files</h3></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>File</th><th>Imported by</th><th>Imports</th></tr></thead>
              <tbody>
                {insights.hub_files.map(h => (
                  <tr key={h.file}>
                    <td><code>{h.file}</code></td>
                    <td>{h.imported_by}</td>
                    <td>{h.imports}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h3>Most complex symbols</h3></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Symbol</th><th>File</th><th>Complexity</th></tr></thead>
              <tbody>
                {insights.complex_symbols.map(s => (
                  <tr key={s.symbol + s.file}>
                    <td><code>{s.symbol}</code></td>
                    <td><code>{s.file}</code></td>
                    <td>{s.complexity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h3>Likely unused symbols ({insights.likely_unused.length})</h3></div>
        {insights.likely_unused.length === 0 ? (
          <p className="ov-muted">— no obvious dead code —</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Symbol</th><th>File</th></tr></thead>
              <tbody>
                {insights.likely_unused.slice(0, 30).map(u => (
                  <tr key={u.symbol + u.file}>
                    <td><code>{u.symbol}</code></td>
                    <td><code>{u.file}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
