import { useEffect, useRef, useState } from 'react';
import { LauncherUser } from '../auth';
import { Icon } from '../components/LauncherUi';
import { AiChatPage } from './AiChatPage';
import { AvatarPage } from './AvatarPage';
import { ProfilePage } from './ProfilePage';
import { SocialPage } from './SocialPage';
import { WorldPage } from './WorldPage';

type LauncherPage = 'home' | 'world' | 'avatar' | 'chat' | 'social' | 'profile';

export function LauncherHome({ user, onLogout, onUserUpdated }: { user: LauncherUser; onLogout: () => void; onUserUpdated: (user: LauncherUser) => void }) {
  const [page, setPage] = useState<LauncherPage>(() => {
    const preview = new URLSearchParams(window.location.search).get('preview');
    return import.meta.env.DEV && (preview === 'world' || preview === 'avatar' || preview === 'chat' || preview === 'social' || preview === 'profile') ? preview : 'home';
  });
  const [launchState, setLaunchState] = useState<'idle' | 'launching'>('idle');
  const [toast, setToast] = useState('');
  const [version, setVersion] = useState('0.3.0');
  const toastTimer = useRef<number | null>(null);
  const mounted = useRef(true);
  const launchInFlight = useRef(false);

  useEffect(() => {
    mounted.current = true;
    if (window.launcher?.app) {
      void window.launcher.app.getVersion().then((nextVersion) => { if (mounted.current) setVersion(nextVersion); }).catch(() => { if (mounted.current) setVersion('未知'); });
    }
    return () => {
      mounted.current = false;
      if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    };
  }, []);

  const showToast = (message: string) => {
    if (!mounted.current) return;
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = window.setTimeout(() => {
      if (mounted.current) setToast('');
      toastTimer.current = null;
    }, 5000);
  };

  const launchGame = async () => {
    if (launchInFlight.current) return;
    launchInFlight.current = true;
    setLaunchState('launching');
    try {
      const result = window.launcher ? await window.launcher.game.launch() : { ok: false, message: '浏览器预览模式无法启动本地游戏。' };
      showToast(result.message || (result.ok ? '游戏已启动。' : '游戏启动失败。'));
    } catch (error) {
      showToast(error instanceof Error ? `游戏启动失败：${error.message}` : '游戏启动失败，请稍后重试。');
    } finally {
      launchInFlight.current = false;
      if (mounted.current) setLaunchState('idle');
    }
  };

  const navigate = (nextPage: LauncherPage) => setPage(nextPage);
  return (
    <main className="launcher-shell">
      <aside className="sidebar">
        <nav aria-label="主要导航">
          <button type="button" className={`nav-item ${page === 'home' ? 'active' : ''}`} aria-current={page === 'home' ? 'page' : undefined} onClick={() => navigate('home')}><Icon name="home"/><span>首页</span></button>
          <button type="button" className={`nav-item ${page === 'world' ? 'active' : ''}`} aria-current={page === 'world' ? 'page' : undefined} onClick={() => navigate('world')}><Icon name="world"/><span>世界</span></button>
          <button type="button" className={`nav-item ${page === 'avatar' || page === 'chat' ? 'active' : ''}`} aria-current={page === 'avatar' || page === 'chat' ? 'page' : undefined} onClick={() => navigate('avatar')}><Icon name="avatar"/><span>虚拟分身</span></button>
          <button type="button" className={`nav-item ${page === 'social' ? 'active' : ''}`} aria-current={page === 'social' ? 'page' : undefined} onClick={() => navigate('social')}><Icon name="friends"/><span>社交</span></button>
        </nav>
        <div className="sidebar-bottom">
          <button type="button" className="nav-item"><Icon name="download"/><span>下载管理</span></button>
          <button type="button" className="nav-item"><Icon name="settings"/><span>设置</span></button>
          <button type="button" className={`profile ${page === 'profile' ? 'active' : ''}`} aria-current={page === 'profile' ? 'page' : undefined} onClick={() => navigate('profile')} title="打开个人主页"><span className="avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><span className="profile-copy"><strong>{user.displayName}</strong><small>在线 · 查看个人主页</small></span><span className="profile-chevron" aria-hidden="true">›</span></button>
        </div>
      </aside>

      {page === 'profile' ? <ProfilePage user={user} onBack={() => navigate('home')} onLogout={onLogout} onUserUpdated={onUserUpdated}/>
        : page === 'world' ? <WorldPage user={user} onLaunch={() => { void launchGame(); }}/>
          : page === 'avatar' ? <AvatarPage user={user} launching={launchState === 'launching'} onLaunch={() => { void launchGame(); }} onChat={() => navigate('chat')}/>
            : page === 'chat' ? <AiChatPage user={user} onBack={() => navigate('avatar')}/>
              : page === 'social' ? <SocialPage user={user}/>
                : <HomeDashboard version={version} launching={launchState === 'launching'} onLaunch={() => { void launchGame(); }}/>} 
      {toast && <div className="toast" role="status" aria-live="polite">{toast}</div>}
    </main>
  );
}

function HomeDashboard({ version, launching, onLaunch }: { version: string; launching: boolean; onLaunch: () => void }) {
  return (
    <section className="home-content">
      <div className="hero-game"><div className="hero-noise" aria-hidden="true"/><div className="planet" aria-hidden="true"/><div className="silhouette" aria-hidden="true"/><div className="hero-copy"><div className="status-pill"><span/> PRE-ALPHA EXPERIENCE</div><h1>ECHO<span>VERSE</span></h1><p className="hero-cn">在世界的另一边，成为另一个你。</p><p className="hero-description">你的数字分身正在等待第一次苏醒。创建性格、探索小镇，并让每一次相遇成为只属于你的故事。</p><div className="hero-actions"><button type="button" className="play-button" onClick={onLaunch} disabled={launching}><span className="play-triangle"/>{launching ? '正在启动…' : '启动游戏'}</button><button type="button" className="secondary-button">查看详情</button></div><div className="game-meta"><span>版本 {version}</span><span>Windows</span><span>简体中文</span></div></div></div>
      <section className="dashboard-row" aria-label="平台动态"><article className="news-card featured"><div className="card-tag">开发日志</div><div><h3>世界正在形成</h3><p>首个主题街区、数字分身系统与离线观察模式进入原型阶段。</p><span>阅读开发进度 →</span></div></article><article className="news-card community"><div className="card-tag">社区</div><div><h3>成为世界的第一批居民</h3><p>关注测试资格、开发者活动与共创计划。</p><span>了解更多 →</span></div></article><article className="activity-card"><div className="activity-head"><h3>分身动态</h3><span>原型模拟</span></div><div className="home-activity-feed"><div><i/><p><strong>人格档案保持在线</strong><span>AI Agent 已准备接收新的经历。</span></p><time>刚刚</time></div><div><i/><p><strong>中央小镇传来微弱信号</strong><span>发现一条尚未解锁的探索路线。</span></p><time>12m</time></div><div><i/><p><strong>伴生模式可以使用</strong><span>点击右上角菱形按钮召唤桌宠。</span></p><time>系统</time></div></div></article></section>
    </section>
  );
}
