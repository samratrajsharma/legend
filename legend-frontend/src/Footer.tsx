import React from 'react';
import './Footer.css';
import Logo from './Logo';
import { DOCS_URL, GITHUB_URL, PYPI_URL } from './links';

const Footer: React.FC = () => (
  <footer className="kn-foot">
    <div className="container kn-foot__inner">
      <span className="kn-foot__brand">
        <Logo className="kn-foot__mark" size={16} />
        Legend
      </span>
      <nav className="kn-foot__links">
        <a href="#how-it-works">How it works</a>
        <a href="#what-you-get">Features</a>
        <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">Docs</a>
        <a href={PYPI_URL} target="_blank" rel="noopener noreferrer">PyPI</a>
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
      </nav>
      <span className="kn-foot__copy">© {new Date().getFullYear()} Legend — open source, local-first.</span>
    </div>
  </footer>
);

export default Footer;
