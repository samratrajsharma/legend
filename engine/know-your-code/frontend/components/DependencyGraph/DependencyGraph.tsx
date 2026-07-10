import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3-force';
import { kycApi, GraphNode, GraphEdge } from '../../api/kycApi';
import './DependencyGraph.css';

const LANG_COLOR: Record<string, string> = {
  python: '#3776ab', javascript: '#f1e05a', typescript: '#3178c6', go: '#00add8',
  java: '#b07219', markdown: '#083fa1', yaml: '#cb171e', json: '#888', other: '#9ca3af',
};
type SimNode = GraphNode & { x: number; y: number; vx?: number; vy?: number };

export default function DependencyGraph({ repoId, ready, full }:
  { repoId: string; ready?: boolean; full?: boolean }) {
  const [data, setData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [sel, setSel] = useState<GraphNode | null>(null);
  const [, setTick] = useState(0);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<any[]>([]);
  const W = full ? 900 : 760;
  const H = full ? 560 : 440;

  useEffect(() => {
    kycApi.getArchitecture(repoId).then((r) => setData(r.data)).catch(() => setData({ nodes: [], edges: [] }));
  }, [repoId]);

  useEffect(() => {
    if (!data || data.nodes.length === 0) return;
    const nodes: SimNode[] = data.nodes.map((n) => ({
      ...n, x: W / 2 + (Math.random() - 0.5) * 80, y: H / 2 + (Math.random() - 0.5) * 80,
    }));
    const links = data.edges.map((e) => ({ source: e.source, target: e.target, type: e.type }));
    nodesRef.current = nodes; linksRef.current = links;
    const sim = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links as any).id((d: any) => d.id).distance(70).strength(0.6))
      .force('charge', d3.forceManyBody().strength(-180))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collide', d3.forceCollide(18))
      .on('tick', () => setTick((t) => t + 1));
    return () => { sim.stop(); };
    // eslint-disable-next-line
  }, [data]);

  const adj = useMemo(() => {
    const m: Record<string, Set<string>> = {};
    (data?.edges || []).forEach((e) => {
      (m[e.source] = m[e.source] || new Set()).add(e.target);
      (m[e.target] = m[e.target] || new Set()).add(e.source);
    });
    return m;
  }, [data]);

  if (ready === false) {
    return <div className="card"><div className="empty-state"><h3>Still indexing</h3>
      <p>The architecture graph appears once indexing finishes.</p></div></div>;
  }
  if (!data) return <div className="dash-loading">Loading…</div>;
  if (data.nodes.length === 0) {
    return <div className="card"><div className="empty-state"><h3>No graph yet</h3>
      <p>No import relationships were detected in this codebase.</p></div></div>;
  }

  const nodes = nodesRef.current;
  const links = linksRef.current;
  const isLit = (id: string) => !hover || hover === id || !!adj[hover]?.has(id);

  return (
    <div className={'kyc-graph' + (sel ? ' kyc-graph--drawer' : '')}>
      <div className="card kyc-graph-canvas">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
          {links.map((l: any, i: number) => {
            const s = l.source, t = l.target;
            if (!s || !t || s.x == null || t.x == null) return null;
            const lit = !hover || s.id === hover || t.id === hover;
            return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
              stroke={lit ? '#8b5cf6' : '#e5e7eb'} strokeWidth={lit ? 1.4 : 0.8} opacity={lit ? 0.8 : 0.35} />;
          })}
          {nodes.map((n) => {
            const lit = isLit(n.id);
            return (
              <g key={n.id} transform={`translate(${n.x},${n.y})`} className="kyc-gnode"
                onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} onClick={() => setSel(n)}>
                <circle r={hover === n.id ? 9 : 6} fill={LANG_COLOR[n.language || 'other'] || '#9ca3af'}
                  opacity={lit ? 1 : 0.3} stroke="#fff" strokeWidth={1.5} />
                {(hover === n.id || full) && (
                  <text x={9} y={4} fontSize={10} fill="var(--dash-text-secondary)" opacity={lit ? 1 : 0.3}>{n.label}</text>
                )}
              </g>
            );
          })}
        </svg>
        <div className="kyc-graph-legend">
          {Array.from(new Set(data.nodes.map((n) => n.language || 'other'))).map((l) => (
            <span key={l} className="kyc-legend-item"><i style={{ background: LANG_COLOR[l] || '#9ca3af' }} />{l}</span>
          ))}
        </div>
      </div>

      {sel && (
        <div className="card kyc-graph-side">
          <div className="card-header"><h3>{sel.label}</h3>
            <button className="btn btn--secondary btn--sm" onClick={() => setSel(null)}>Close</button></div>
          <div className="kyc-graph-detail">
            <div><span>Path</span><code>{sel.id}</code></div>
            <div><span>Language</span><code>{sel.language || '—'}</code></div>
            <div><span>Linked files</span><code>{adj[sel.id] ? adj[sel.id].size : 0}</code></div>
          </div>
        </div>
      )}
    </div>
  );
}
