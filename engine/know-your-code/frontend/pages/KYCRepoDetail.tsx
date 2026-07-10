import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { kycApi, Repo, FileNode } from '../api/kycApi';
import KycChip from '../components/KycChip/KycChip';
import FileTreeViewer from '../components/FileTreeViewer/FileTreeViewer';
import CodeBlock from '../components/CodeBlock/CodeBlock';
import QAChatPanel from '../components/QAChatPanel/QAChatPanel';
import DependencyGraph from '../components/DependencyGraph/DependencyGraph';
import KYCOnboarding from './KYCOnboarding';
import '../kyc.css';
import './KYCRepoDetail.css';

const TABS = ['Overview', 'Files', 'Q&A', 'Architecture', 'Onboarding Tour'];
const fmt = (n: any) => (typeof n === 'number' ? n.toLocaleString() : (n ?? '—'));

function statusLabel(r: Repo) {
  if (r.status === 'ready') return 'Ready';
  if (r.status === 'failed') return 'Indexing failed';
  return 'Indexing…';
}

function Overview({ repo }: { repo: Repo }) {
  const s = repo.stats || {};
  const cards: [string, any][] = [
    ['Files', fmt(s.files)], ['Lines of code', fmt(s.loc)],
    ['Symbols indexed', fmt(s.symbols)], ['Languages', Array.isArray(s.langs) ? s.langs.length : 0],
  ];
  return (
    <div>
      <div className="kyc-stats">
        {cards.map(([k, v]) => (
          <div key={k} className="kyc-stat-card">
            <div className="kyc-stat-label">{k}</div>
            <div className="kyc-stat-value">{v}</div>
          </div>
        ))}
      </div>
      {Array.isArray(s.langs) && s.langs.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Languages</h3></div>
          <div className="chip-list">{s.langs.map((l: string) => <span key={l} className="chip">{l}</span>)}</div>
        </div>
      )}
    </div>
  );
}

function FilesTab({ repoId }: { repoId: string }) {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [sel, setSel] = useState<FileNode | null>(null);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    kycApi.listFiles(repoId).then((r) => setFiles(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, [repoId]);
  const open = (f: FileNode) => {
    setSel(f); setContent('');
    kycApi.fileContent(repoId, f.id).then((r) => setContent(r.data.content)).catch(() => {});
  };
  if (loading) return <div className="dash-loading">Loading…</div>;
  return (
    <div className="two-col kyc-files">
      <div className="card">
        <div className="card-header"><h3>Files</h3></div>
        <FileTreeViewer files={files} onSelect={open} selectedId={sel?.id} />
      </div>
      <div className="card">
        <div className="card-header"><h3>{sel ? sel.path : 'Select a file'}</h3></div>
        {sel ? <CodeBlock code={content} language={sel.language} />
             : <div className="empty-state"><p>Pick a file to view its source.</p></div>}
      </div>
    </div>
  );
}

export default function KYCRepoDetail() {
  const { id = '' } = useParams();
  const nav = useNavigate();
  const [repo, setRepo] = useState<Repo | null>(null);
  const [tab, setTab] = useState('Overview');
  const timer = useRef<any>(null);

  const fetchRepo = () => kycApi.getRepo(id).then((r) => setRepo(r.data)).catch(() => {});
  useEffect(() => { fetchRepo(); /* eslint-disable-next-line */ }, [id]);
  useEffect(() => {
    if (repo?.status === 'indexing') {
      timer.current = setInterval(fetchRepo, 2000);
      return () => clearInterval(timer.current);
    }
    if (timer.current) clearInterval(timer.current);
    // eslint-disable-next-line
  }, [repo?.status]);

  if (!repo) return <div className="dash-loading">Loading…</div>;
  const s = repo.stats || {};
  const p = repo.progress || {};
  return (
    <div>
      <div className="page-header kyc-head">
        <div>
          <button className="kyc-back" onClick={() => nav('/app/know-your-code/repos')}>← Codebases</button>
          <h1>{repo.name}</h1>
          <p>
            {statusLabel(repo)}
            {Array.isArray(s.langs) && s.langs.length ? ' · ' + s.langs.join(' · ') : ''}
            {s.loc ? ' · ' + fmt(s.loc) + ' LOC' : ''}
          </p>
        </div>
        <KycChip />
      </div>

      {repo.status === 'indexing' && (
        <div className="card kyc-progress-card">
          <div className="kyc-prog-row">
            <span><orc-spinner size="sm" /> {p.step || 'indexing'}…</span>
            <span>{p.pct || 0}%</span>
          </div>
          <div className="progress-bar"><div className="progress-bar__fill" style={{ width: `${p.pct || 0}%` }} /></div>
        </div>
      )}
      {repo.status === 'failed' && (
        <div className="kyc-toast kyc-toast--err">Indexing failed: {p.error || 'unknown error'}</div>
      )}

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={'tab' + (tab === t ? ' tab--active' : '')} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && <Overview repo={repo} />}
      {tab === 'Files' && <FilesTab repoId={id} />}
      {tab === 'Q&A' && <QAChatPanel repoId={id} ready={repo.status === 'ready'} />}
      {tab === 'Architecture' && <DependencyGraph repoId={id} ready={repo.status === 'ready'} />}
      {tab === 'Onboarding Tour' && <KYCOnboarding repoId={id} embedded />}
    </div>
  );
}
