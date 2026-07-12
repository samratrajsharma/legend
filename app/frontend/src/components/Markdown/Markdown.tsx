import { ReactNode } from 'react';
import './Markdown.css';

// A small, dependency-free, XSS-safe markdown renderer. Everything becomes React
// text nodes / elements (no dangerouslySetInnerHTML), so untrusted README content
// from an arbitrary repo cannot inject script. Covers the constructs READMEs use:
// headings, bold/italic/strike, inline + fenced code, links, images (as text),
// blockquotes, ordered/unordered lists, tables, and horizontal rules.

function safeUrl(url: string): string {
  const u = (url || '').trim();
  if (/^(https?:|mailto:|#|\/|\.\/|\.\.\/)/i.test(u)) return u;
  if (/^[\w.][\w./#?=&%-]*$/.test(u)) return u;   // relative-ish path
  return '#';                                       // block javascript:, data:, etc.
}

function parseInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let key = 0;
  const patterns: { re: RegExp; make: (m: RegExpMatchArray, k: number) => ReactNode }[] = [
    { re: /`([^`]+)`/,             make: (m, k) => <code key={k} className="md-code">{m[1]}</code> },
    { re: /\*\*([^*]+)\*\*/,       make: (m, k) => <strong key={k}>{parseInline(m[1])}</strong> },
    { re: /__([^_]+)__/,           make: (m, k) => <strong key={k}>{parseInline(m[1])}</strong> },
    { re: /~~([^~]+)~~/,           make: (m, k) => <del key={k}>{parseInline(m[1])}</del> },
    { re: /\*([^*\n]+)\*/,         make: (m, k) => <em key={k}>{parseInline(m[1])}</em> },
    { re: /(?<![\w])_([^_\n]+)_(?![\w])/, make: (m, k) => <em key={k}>{parseInline(m[1])}</em> },
    { re: /!\[([^\]]*)\]\(([^)]+)\)/, make: (m, k) => <span key={k} className="md-imgtag">[image: {m[1] || 'image'}]</span> },
    { re: /\[([^\]]+)\]\(([^)]+)\)/,  make: (m, k) => <a key={k} className="md-link" href={safeUrl(m[2])} target="_blank" rel="noopener noreferrer">{parseInline(m[1])}</a> },
  ];
  let guard = 0;
  while (rest && guard++ < 5000) {
    let best: RegExpMatchArray | null = null;
    let bestIdx = Infinity;
    let bestMake: ((m: RegExpMatchArray, k: number) => ReactNode) | null = null;
    for (const p of patterns) {
      const m = rest.match(p.re);
      if (m && m.index !== undefined && m.index < bestIdx) {
        best = m; bestIdx = m.index; bestMake = p.make;
      }
    }
    if (!best || !bestMake) { out.push(rest); break; }
    if (bestIdx > 0) out.push(rest.slice(0, bestIdx));
    out.push(bestMake(best, key++));
    rest = rest.slice(bestIdx + best[0].length);
  }
  return out;
}

function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|')) s = s.slice(0, -1);
  return s.split('|').map(c => c.trim());
}

const BLOCK_START = /^(#{1,6}\s|```|\s*>|\s*([-*+]|\d+\.)\s)/;

export default function Markdown({ text }: { text: string }) {
  const lines = (text || '').replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let i = 0, k = 0;

  while (i < lines.length) {
    const line = lines[i];

    // fenced code block
    if (/^\s*```/.test(line)) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^\s*```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      blocks.push(<pre key={k++} className="md-pre"><code>{buf.join('\n')}</code></pre>);
      continue;
    }

    // heading
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      const lvl = Math.min(h[1].length, 6);
      const HTag = (`h${lvl}`) as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
      blocks.push(<HTag key={k++} className={`md-h md-h${lvl}`}>{parseInline(h[2].replace(/#+\s*$/, ''))}</HTag>);
      i++; continue;
    }

    // horizontal rule
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { blocks.push(<hr key={k++} className="md-hr" />); i++; continue; }

    // blockquote
    if (/^\s*>/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) { buf.push(lines[i].replace(/^\s*>\s?/, '')); i++; }
      blocks.push(<blockquote key={k++} className="md-quote"><Markdown text={buf.join('\n')} /></blockquote>);
      continue;
    }

    // table (header row + |---| separator)
    if (line.includes('|') && i + 1 < lines.length &&
        /\|/.test(lines[i + 1]) && /^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/.test(lines[i + 1])) {
      const header = splitRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) { rows.push(splitRow(lines[i])); i++; }
      blocks.push(
        <div key={k++} className="md-table-wrap">
          <table className="md-table">
            <thead><tr>{header.map((c, ci) => <th key={ci}>{parseInline(c)}</th>)}</tr></thead>
            <tbody>{rows.map((r, ri) => <tr key={ri}>{header.map((_, ci) => <td key={ci}>{parseInline(r[ci] || '')}</td>)}</tr>)}</tbody>
          </table>
        </div>
      );
      continue;
    }

    // list (consume consecutive items)
    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, '')); i++;
      }
      const inner = items.map((it, ii) => <li key={ii}>{parseInline(it)}</li>);
      blocks.push(ordered ? <ol key={k++} className="md-list">{inner}</ol> : <ul key={k++} className="md-list">{inner}</ul>);
      continue;
    }

    // blank
    if (!line.trim()) { i++; continue; }

    // paragraph
    const buf: string[] = [line]; i++;
    while (i < lines.length && lines[i].trim() && !BLOCK_START.test(lines[i]) && !lines[i].includes('|')) { buf.push(lines[i]); i++; }
    blocks.push(<p key={k++} className="md-p">{parseInline(buf.join(' '))}</p>);
  }

  return <div className="md">{blocks}</div>;
}
