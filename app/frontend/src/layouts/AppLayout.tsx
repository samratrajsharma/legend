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

const HomeIcon = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M2.5 6.8L8 2.5l5.5 4.3v6a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1v-6z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
  </svg>
);
const GearIcon = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.3" />
    <path d="M8 1.7v1.4M8 12.9v1.4M14.3 8h-1.4M3.1 8H1.7M12.4 3.6l-1 1M4.6 11.4l-1 1M12.4 12.4l-1-1M4.6 4.6l-1-1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
  </svg>
);
const CloseIcon = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
    <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

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

        <div className="sidebar__section sidebar__section--nav">
          <NavLink to="/" end className={({ isActive }) => `sidebar__link${isActive ? ' sidebar__link--active' : ''}`}>
            <HomeIcon />
            <span>Home</span>
          </NavLink>
        </div>

        <div className="sidebar__section">
          <div className="sidebar__section-label">Repositories</div>
          {repos.length === 0 ? (
            <div className="sidebar__empty">None connected yet</div>
          ) : repos.map(r => (
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
                onClick={() => removeRepo(r.repo_id)}><CloseIcon /></button>
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
          <NavLink to="/settings" className={({ isActive }) => `sidebar__link${isActive ? ' sidebar__link--active' : ''}`}>
            <GearIcon />
            <span>Settings</span>
          </NavLink>
          <div className="sidebar__llm" title={llm?.configured ? `Model: ${llm.model}` : 'No model configured'}>
            <span className={`sidebar__llm-dot${llm?.configured ? ' sidebar__llm-dot--on' : ''}`} />
            <span className="sidebar__llm-text">
              {llm?.configured ? `LLM: ${llm.model}` : 'LLM: not set'}
            </span>
          </div>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
