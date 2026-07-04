/**
 * orc-spinner — the same Orchestraty logo-spinning web component.
 * Copied verbatim so each testbed is self-contained.
 */
class OrcSpinnerElement extends HTMLElement {
  connectedCallback() {
    const size = this.getAttribute('size') || 'md';
    const dim = size === 'sm' ? 20 : size === 'lg' ? 48 : 32;
    this.innerHTML = `<img
      src="/orchestraty-icon.svg"
      alt="Loading"
      width="${dim}"
      height="${dim}"
      style="
        width:${dim}px;height:${dim}px;
        display:inline-block;
        animation:orc-spin 1.2s linear infinite;
        transform-origin:50% 50%;
        will-change:transform;
      "
    />`;
  }
}

if (!customElements.get('orc-spinner')) {
  customElements.define('orc-spinner', OrcSpinnerElement);
}

if (!document.getElementById('orc-keyframes')) {
  const style = document.createElement('style');
  style.id = 'orc-keyframes';
  style.textContent = '@keyframes orc-spin { to { transform: rotate(360deg); } }';
  document.head.appendChild(style);
}

// Type augmentation for JSX
declare global {
  namespace JSX {
    interface IntrinsicElements {
      'orc-spinner': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        size?: 'sm' | 'md' | 'lg';
      };
    }
  }
}

export {};
