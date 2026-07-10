import { useEffect, useRef } from 'react';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import 'prismjs/components/prism-clike';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-go';
import 'prismjs/components/prism-java';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-markdown';
import './CodeBlock.css';

const LANG_MAP: Record<string, string> = {
  python: 'python', javascript: 'javascript', typescript: 'typescript', go: 'go', java: 'java',
  markdown: 'markdown', yaml: 'yaml', json: 'json', other: 'clike',
};

export default function CodeBlock({ code, language }: { code: string; language: string }) {
  const ref = useRef<HTMLElement>(null);
  const lang = LANG_MAP[language] || 'clike';
  useEffect(() => { if (ref.current) Prism.highlightElement(ref.current); }, [code, lang]);
  if (code === '') return <div className="dash-loading">Loading…</div>;
  return <pre className="kyc-code"><code ref={ref} className={`language-${lang}`}>{code}</code></pre>;
}
