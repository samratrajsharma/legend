import { Component, ErrorInfo, ReactNode } from 'react';

type Props = {
  children: ReactNode;
  /** changes to this value reset the boundary — e.g. the current route key, so a
   *  render error on one page doesn't wedge the whole app after navigation. */
  resetKey?: unknown;
};
type State = { error: Error | null };

/**
 * Catches render-time exceptions in its subtree and shows a recoverable fallback instead
 * of React unmounting the whole app to a blank white screen (QA #19). Resets automatically
 * when `resetKey` changes (navigation) and offers a manual retry / reload.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface it in the console for debugging; no telemetry is sent anywhere.
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="card" role="alert" style={{ margin: 24, maxWidth: 640 }}>
          <div className="card-header"><h3>Something went wrong on this screen</h3></div>
          <p style={{ color: 'var(--kyc-muted, #a7a7a7)', marginTop: 8 }}>
            The page hit an unexpected error and stopped rendering. Your indexed repos are
            unaffected — you can retry this screen or reload the app.
          </p>
          <pre style={{
            whiteSpace: 'pre-wrap', fontSize: 12, opacity: 0.8, marginTop: 12,
            maxHeight: 160, overflow: 'auto',
          }}>{this.state.error.message}</pre>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button type="button" className="btn btn--primary"
              onClick={() => this.setState({ error: null })}>Retry</button>
            <button type="button" className="btn"
              onClick={() => window.location.reload()}>Reload app</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
