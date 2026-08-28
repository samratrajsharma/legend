import React from 'react';
import './Footer.css';
import Logo from './Logo';
import { DOCS_URL, GITHUB_URL, PYPI_URL } from './links';

const Footer: React.FC = () => (
  <footer className="lg-foot">
    <div className="container lg-foot__inner">
      <span className="lg-foot__brand">
        <Logo className="lg-foot__mark" size={16} />
        Legend
      </span>
      <nav className="lg-foot__links">
        <a href="#how-it-works">How it works</a>
        <a href="#what-you-get">Features</a>
        <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">Docs</a>
        <a href={PYPI_URL} target="_blank" rel="noopener noreferrer">PyPI</a>
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
      </nav>
      <span className="lg-foot__copy">© {new Date().getFullYear()} Legend — open source, local-first.</span>
    </div>
  </footer>
);

export default Footer;
