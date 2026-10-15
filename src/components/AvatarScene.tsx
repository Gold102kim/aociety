import { lazy, Suspense, useEffect, useState } from 'react';
import { ErrorBoundary } from './ErrorBoundary';

const AvatarViewport = lazy(() => import('../AvatarViewport').then((module) => ({ default: module.AvatarViewport })));
export type AvatarLoadStatus = 'loading' | 'ready' | 'error';

function AvatarViewportFallback() {
  return (
    <div className="avatar-viewport avatar-viewport-fallback" role="status" aria-live="polite">
      <div className="avatar-viewport-state"><i aria-hidden="true"/><span>正在准备 3D 分身</span></div>
    </div>
  );
}

function AvatarViewportError({ onRetry, onStatusChange }: { onRetry: () => void; onStatusChange?: (status: AvatarLoadStatus) => void }) {
  useEffect(() => { onStatusChange?.('error'); }, [onStatusChange]);
  return (
    <div className="avatar-viewport avatar-viewport-fallback" role="alert">
      <div className="avatar-viewport-state error">
        <strong aria-hidden="true">!</strong>
        <span>3D 分身暂时无法显示</span>
        <span>外观不可用不影响文字对话。</span>
        <button type="button" onClick={onRetry}>重试外观</button>
      </div>
    </div>
  );
}

export function AvatarScene({ variant, onStatusChange }: { variant: 'preview' | 'companion'; onStatusChange?: (status: AvatarLoadStatus) => void }) {
  const [attempt, setAttempt] = useState(0);
  const retry = () => { onStatusChange?.('loading'); setAttempt((current) => current + 1); };
  return (
    <ErrorBoundary key={attempt} fallback={() => <AvatarViewportError onRetry={retry} onStatusChange={onStatusChange}/>}>
      <Suspense fallback={<AvatarViewportFallback/>}>
        <AvatarViewport variant={variant} onRetry={retry} onStatusChange={onStatusChange}/>
      </Suspense>
    </ErrorBoundary>
  );
}
