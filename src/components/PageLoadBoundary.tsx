import { ReactNode, Suspense } from 'react';
import { ErrorBoundary } from './ErrorBoundary';

export function PageLoadBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary fallback={() => <section className="page-loading" role="alert"><p>页面载入失败，请重新载入。</p><button type="button" onClick={() => window.location.reload()}>重新载入</button></section>}>
      <Suspense fallback={<section className="page-loading" role="status" aria-live="polite">正在准备页面…</section>}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}
