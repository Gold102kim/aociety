import { lazy, Suspense } from 'react';
import { ErrorBoundary } from './ErrorBoundary';

const AvatarViewport = lazy(() => import('../AvatarViewport').then((module) => ({ default: module.AvatarViewport })));

function AvatarViewportFallback() {
  return (
    <div className="avatar-viewport avatar-viewport-fallback" role="status" aria-live="polite">
      <div className="avatar-viewport-state"><i aria-hidden="true"/><span>正在准备 3D 分身</span></div>
    </div>
  );
}

function AvatarViewportError() {
  return (
    <div className="avatar-viewport avatar-viewport-fallback" role="alert">
      <div className="avatar-viewport-state error">
        <strong aria-hidden="true">!</strong>
        <span>3D 分身暂时无法显示</span>
        <button type="button" onClick={() => window.location.reload()}>重新载入</button>
      </div>
    </div>
  );
}

export function AvatarScene({ variant }: { variant: 'preview' | 'companion' }) {
  return (
    <ErrorBoundary fallback={() => <AvatarViewportError/>}>
      <Suspense fallback={<AvatarViewportFallback/>}>
        <AvatarViewport variant={variant}/>
      </Suspense>
    </ErrorBoundary>
  );
}
