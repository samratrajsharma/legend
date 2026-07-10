import { useMemo, useState } from 'react';
import { FileNode } from '../../api/kycApi';
import './FileTreeViewer.css';

type TreeNode = { name: string; path: string; children: Record<string, TreeNode>; file?: FileNode };

function buildTree(files: FileNode[]): TreeNode {
  const root: TreeNode = { name: '', path: '', children: {} };
  for (const f of files) {
    const parts = f.path.split('/');
    let cur = root;
    parts.forEach((part, i) => {
      const p = parts.slice(0, i + 1).join('/');
      if (!cur.children[part]) cur.children[part] = { name: part, path: p, children: {} };
      cur = cur.children[part];
      if (i === parts.length - 1) cur.file = f;
    });
  }
  return root;
}

function Node({ node, depth, onSelect, selectedId }:
  { node: TreeNode; depth: number; onSelect: (f: FileNode) => void; selectedId?: string }) {
  const [open, setOpen] = useState(depth < 1);
  const kids = Object.values(node.children).sort((a, b) => {
    const ad = Object.keys(a.children).length ? 0 : 1;
    const bd = Object.keys(b.children).length ? 0 : 1;
    return ad - bd || a.name.localeCompare(b.name);
  });
  if (node.file && kids.length === 0) {
    const sel = node.file.id === selectedId;
    return (
      <div className={'kyc-tree-file' + (sel ? ' kyc-tree-file--sel' : '')}
           style={{ paddingLeft: depth * 14 + 10 }} onClick={() => onSelect(node.file!)}>
        {node.name}
      </div>
    );
  }
  return (
    <div>
      {node.name && (
        <div className="kyc-tree-dir" style={{ paddingLeft: depth * 14 + 4 }} onClick={() => setOpen((o) => !o)}>
          <span className="kyc-tree-caret">{open ? '▾' : '▸'}</span>{node.name}
        </div>
      )}
      {open && kids.map((k) => (
        <Node key={k.path} node={k} depth={node.name ? depth + 1 : depth} onSelect={onSelect} selectedId={selectedId} />
      ))}
    </div>
  );
}

export default function FileTreeViewer({ files, onSelect, selectedId }:
  { files: FileNode[]; onSelect: (f: FileNode) => void; selectedId?: string }) {
  const tree = useMemo(() => buildTree(files), [files]);
  if (!files.length) return <div className="empty-state"><p>No files.</p></div>;
  return (
    <div className="kyc-tree">
      {Object.values(tree.children).map((k) => (
        <Node key={k.path} node={k} depth={0} onSelect={onSelect} selectedId={selectedId} />
      ))}
    </div>
  );
}
