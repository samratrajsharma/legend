import { useEffect, useState } from 'react';
import { NavLink, Outlet, useParams, useNavigate, Link } from 'react-router-dom';
import { kycApi, RepoListItem } from '../api/client';
import './AppLayout.css';

const NAV_TABS = [
  { to: 'overview',  label: 'Overview' },
  { to: 'timeline',  label: 'Timeline' },
  { to: 'files',     label: 'Files' },
  { to: 'diagrams',  label: 'Diagrams' },
  { to: 'api-db',    label: 'API & DB' },
  { to: 'ask',       label: 'Ask' },
  { to: 'track',     label: 'Track' },
  { to: 'intel',     label: 'Intel' },
] as const;

export default function AppLayout() {
  const [repos, setRepos] = useState<RepoListItem[]>([]);
  const [llm, setLlm] = useState<{ configured: boolean; model: string | null } | null>(null);
  const { repoId } = useParams<{ repoId: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    kycApi.listRepos().then(r => setRepos(r.data)).catch(() => {});
    kycApi.llmStatus().then(r => setLlm(r.data)).catch(() => {});
  }, [repoId]);

  const currentRepo = repos.find(r => r.repo_id === repoId);

  const removeRepo = (rid: string) => {
    kycApi.deleteRepo(rid).catch(() => {}).finally(() => {
      kycApi.listRepos().then(r => setRepos(r.data)).catch(() => {});
      if (rid === repoId) navigate('/');
    });
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <Link to="/" className="sidebar__brand">
          <img src="/orchestraty-icon.svg" width={28} height={28} alt="" />
          <div>
            <div className="sidebar__brand-name">Know Your Code</div>
            <div className="sidebar__brand-sub">Testbed</div>
          </div>
        </Link>

        <div className="sidebar__section">
          <div className="sidebar__section-label">Repositories</div>
          <NavLink to="/" end className={({ isActive }) => `sidebar__link${isActive ? ' sidebar__link--active' : ''}`}>
            <span>Home</span>
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => `sidebar__link${isActive ? ' sidebar__link--active' : ''}`}>
            <span>Settings</span>
          </NavLink>
          {repos.map(r => (
            <div
              key={r.repo_id}
              className={`sidebar__repo${r.repo_id === repoId ? ' sidebar__repo--active' : ''}`}
              title={r.source}
            >
              <button type="button" className="sidebar__repo-open"
                onClick={() => navigate(`/repos/${r.repo_id}/overview`)}>
                <span className="sidebar__repo-name">{r.name}</span>
                <span className={`sidebar__repo-status sidebar__repo-status--${r.status}`}>{r.status}</span>
              </button>
              <button type="button" className="sidebar__repo-x" title="Remove from list"
                onClick={() => removeRepo(r.repo_id)}>×</button>
            </div>
          ))}
        </div>

        {repoId && currentRepo && (
          <div className="sidebar__section">
            <div className="sidebar__section-label">{currentRepo.name}</div>
            {NAV_TABS.map(tab => (
              <NavLink
                key={tab.to}
                to={`/repos/${repoId}/${tab.to}`}
                className={({ isActive }) => `sidebar__link${isActive ? ' sidebar__link--active' : ''}`}
              >
                <span>{tab.label}</span>
              </NavLink>
            ))}
          </div>
        )}

        <div className="sidebar__foot">
          <Link to="/settings" className="sidebar__llm" title="AI / LLM settings">
            <span className={`sidebar__llm-dot${llm?.configured ? ' sidebar__llm-dot--on' : ''}`} />
            <span className="sidebar__llm-text">
              {llm?.configured ? `LLM: ${llm.model}` : 'LLM: not set — configure'}
            </span>
            <span className="sidebar__llm-gear">⚙</span>
          </Link>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
