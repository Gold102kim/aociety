import { Component, ErrorInfo, ReactNode } from 'react';

type ErrorFallback = (error: Error, reset: () => void) => ReactNode;

type ErrorBoundaryProps = {
  children: ReactNode;
  fallback: ErrorFallback;
};

type ErrorBoundaryState = {
  error: Error | null;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('EchoVerse renderer error', error, info.componentStack);
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) return this.props.fallback(this.state.error, this.reset);
    return this.props.children;
  }
}

export function RootErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary fallback={(error) => (
      <main className="fatal-error" role="alert" aria-live="assertive">
        <div className="fatal-error-card">
          <span>ECHOVERSE RECOVERY</span>
          <h1>软件界面遇到意外问题</h1>
          <p>你的账户数据没有被删除。重新载入界面通常即可恢复。</p>
          {import.meta.env.DEV && <details><summary>开发信息</summary><pre>{error.message}</pre></details>}
          <button type="button" className="primary-button" onClick={() => window.location.reload()}>重新载入软件</button>
        </div>
      </main>
    )}>
      {children}
    </ErrorBoundary>
  );
}
