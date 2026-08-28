import { useEffect, useRef } from 'react';

/**
 * Wire an overlay as an accessible modal dialog (QA audit): when `open`, focus moves into the
 * panel, Tab is trapped inside it, Esc closes it, and focus is restored to whatever opened it
 * on close. Returns a ref to spread onto the panel element, which should also carry
 * role="dialog" aria-modal="true" and tabIndex={-1}.
 */
export function useModalDialog<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const panelRef = useRef<T | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    returnFocus.current = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;

    const focusables = () =>
      Array.from(
        panel?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), textarea, select, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter(el => el.offsetParent !== null);

    (focusables()[0] ?? panel)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
      if (e.key !== 'Tab') return;
      const els = focusables();
      if (els.length === 0) { e.preventDefault(); return; }
      const first = els[0];
      const last = els[els.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && (active === first || !panel?.contains(active))) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault(); first.focus();
      }
    };

    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      returnFocus.current?.focus?.();
    };
  }, [open, onClose]);

  return panelRef;
}
