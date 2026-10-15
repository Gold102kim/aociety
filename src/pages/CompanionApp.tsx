import { useEffect, useState } from 'react';
import { AvatarScene, type AvatarLoadStatus } from '../components/AvatarScene';
import { getThemeStyle } from '../theme';

type CompanionState = {
  displayName: string;
  agentStatus: 'WAITING_FOR_PROFILE' | 'READY';
  favoriteColor: string;
};

export function CompanionApp() {
  const [avatarStatus, setAvatarStatus] = useState<AvatarLoadStatus>('loading');
  const [state, setState] = useState<CompanionState>({
    displayName: 'Echo',
    agentStatus: 'WAITING_FOR_PROFILE',
    favoriteColor: new URLSearchParams(window.location.search).get('themeColor') || '薄荷绿',
  });

  useEffect(() => {
    document.body.classList.add('companion-mode');
    document.documentElement.classList.add('companion-mode');
    let active = true;
    if (window.launcher?.companion) {
      void window.launcher.companion.getState().then((nextState) => { if (active) setState(nextState); }).catch(() => undefined);
    }
    return () => {
      active = false;
      document.body.classList.remove('companion-mode');
      document.documentElement.classList.remove('companion-mode');
    };
  }, []);

  return (
    <main className="companion-root" style={getThemeStyle(state.favoriteColor)} title="拖动我移动位置，双击恢复主界面" onDoubleClick={() => window.launcher?.companion.restore()}>
      <div className="companion-actions">
        <button type="button" aria-label="恢复主界面" title="恢复主界面" onClick={() => window.launcher?.companion.restore()}>↗</button>
        <button type="button" aria-label="退出软件" title="退出软件" onClick={() => window.launcher?.companion.quit()}>×</button>
      </div>
      <div className="companion-name"><i aria-hidden="true"/>{state.displayName} · {avatarStatus === 'ready' ? '桌面伴生' : avatarStatus === 'error' ? '外观不可用' : '载入外观中'}</div>
      <section className="companion-avatar" aria-label={`${state.displayName} 的桌面虚拟分身`}><div className="companion-glow" aria-hidden="true"/><AvatarScene variant="companion" onStatusChange={setAvatarStatus}/></section>
      <div className="companion-shadow" aria-hidden="true"/><p>双击恢复平台</p>
    </main>
  );
}
