import { lazy, useEffect, useRef, useState } from 'react';
import { LauncherUser } from '../auth';
import { Icon } from '../components/LauncherUi';
import { AiChatPage } from './AiChatPage';
import { PageLoadBoundary } from '../components/PageLoadBoundary';
import { version as buildVersion } from '../../package.json';

const AvatarPage = lazy(() => import('./AvatarPage').then((module) => ({ default: module.AvatarPage })));
const ProfilePage = lazy(() => import('./ProfilePage').then((module) => ({ default: module.ProfilePage })));
const SocialPage = lazy(() => import('./SocialPage').then((module) => ({ default: module.SocialPage })));
const WorldPage = lazy(() => import('./WorldPage').then((module) => ({ default: module.WorldPage })));

type LauncherPage = 'home' | 'world' | 'avatar' | 'chat' | 'social' | 'profile';

export function LauncherHome({ user, onLogout, onUserUpdated }: { user: LauncherUser; onLogout: () => void; onUserUpdated: (user: LauncherUser) => void }) {
  const [page, setPage] = useState<LauncherPage>(() => {
    const preview = new URLSearchParams(window.location.search).get('preview');
    return import.meta.env.DEV && (preview === 'world' || preview === 'avatar' || preview === 'chat' || preview === 'social' || preview === 'profile') ? preview : 'home';
  });
  const [launchState, setLaunchState] = useState<'idle' | 'launching'>('idle');
  const [chatOpened, setChatOpened] = useState(page === 'chat');
  const [toast, setToast] = useState('');
  const [version, setVersion] = useState(buildVersion);
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

  const navigate = (nextPage: LauncherPage) => {
    if (nextPage === 'chat') setChatOpened(true);
    setPage(nextPage);
  };
  return (
    <main className="launcher-shell">
      <aside className="sidebar">
        <div className="sidebar-heading"><span>你的空间</span><small>PERSONAL SPACE</small></div>
        <nav aria-label="主要导航">
          <button type="button" className={`nav-item ${page === 'home' ? 'active' : ''}`} aria-current={page === 'home' ? 'page' : undefined} onClick={() => navigate('home')}><Icon name="home"/><span>首页</span></button>
          <button type="button" className={`nav-item ${page === 'world' ? 'active' : ''}`} aria-current={page === 'world' ? 'page' : undefined} onClick={() => navigate('world')}><Icon name="world"/><span>世界</span></button>
          <button type="button" className={`nav-item ${page === 'avatar' ? 'active' : ''}`} aria-current={page === 'avatar' ? 'page' : undefined} onClick={() => navigate('avatar')}><Icon name="avatar"/><span>虚拟分身</span></button>
          <button type="button" className={`nav-item ${page === 'chat' ? 'active' : ''}`} aria-current={page === 'chat' ? 'page' : undefined} onClick={() => navigate('chat')}><Icon name="chat"/><span>AI 对话</span></button>
          <button type="button" className={`nav-item ${page === 'social' ? 'active' : ''}`} aria-current={page === 'social' ? 'page' : undefined} onClick={() => navigate('social')}><Icon name="friends"/><span>社交</span></button>
        </nav>
        <div className="sidebar-bottom">
          <button type="button" className="nav-item" onClick={() => showToast('当前版本使用本地游戏文件，暂不提供在线下载。')}><Icon name="download"/><span>下载管理</span></button>
          <button type="button" className="nav-item" onClick={() => showToast('游戏画面设置可在游戏主菜单的“游戏设置”中调整。')}><Icon name="settings"/><span>设置</span></button>
          <button type="button" className={`profile ${page === 'profile' ? 'active' : ''}`} aria-current={page === 'profile' ? 'page' : undefined} onClick={() => navigate('profile')} title="打开个人主页"><span className="avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><span className="profile-copy"><strong>{user.displayName}</strong><small>查看个人档案</small></span><span className="profile-chevron" aria-hidden="true">›</span></button>
        </div>
      </aside>

      <PageLoadBoundary>{page === 'profile' ? <ProfilePage user={user} onBack={() => navigate('home')} onLogout={onLogout} onUserUpdated={onUserUpdated}/>
        : page === 'world' ? <WorldPage user={user} launching={launchState === 'launching'} onLaunch={() => { void launchGame(); }}/>
          : page === 'avatar' ? <AvatarPage user={user} launching={launchState === 'launching'} onLaunch={() => { void launchGame(); }} onChat={() => navigate('chat')}/>
            : page === 'chat' ? null
              : page === 'social' ? <SocialPage user={user}/>
                : <HomeDashboard user={user} version={version} launching={launchState === 'launching'} onLaunch={() => { void launchGame(); }} onNavigate={navigate}/>}</PageLoadBoundary>
      {chatOpened && <AiChatPage key={user.id} user={user} active={page === 'chat'} onBack={() => navigate('avatar')}/>}
      {toast && <div className="toast" role="status" aria-live="polite"><span>{toast}</span><button type="button" aria-label="关闭提示" onClick={() => setToast('')}>×</button></div>}
    </main>
  );
}

function HomeDashboard({ user, version, launching, onLaunch, onNavigate }: { user: LauncherUser; version: string; launching: boolean; onLaunch: () => void; onNavigate: (page: LauncherPage) => void }) {
  const shortcuts = [
    { page: 'avatar' as const, icon: 'avatar' as const, title: '我的虚拟分身', description: '查看形象与性格，认识另一个你。', tag: 'PERSONA' },
    { page: 'chat' as const, icon: 'chat' as const, title: '与 AI 对话', description: '分享今天的想法，让了解从交流开始。', tag: 'CONVERSATION' },
    { page: 'world' as const, icon: 'world' as const, title: '探索世界', description: '了解森林小镇和当前的开发进度。', tag: 'DISCOVERY' },
  ];
  return (
    <section className="home-content">
      <div className="home-container">
        <header className="welcome-header"><div><span className="eyebrow">AOCIETY · ECHOVERSE</span><h1>欢迎回来，{user.displayName}<span className="welcome-dot">。</span></h1><p>一个属于你的分身，一段慢慢发生的故事。</p></div><span className="release-badge">体验版 <b>v{version}</b></span></header>
        <article className="town-hero">
          <img className="town-illustration" src="./illustrations/forest-town.svg" alt=""/>
          <div className="town-hero-copy"><span className="hero-label"><i aria-hidden="true"/> 你的下一站</span><h2>走进森林小镇</h2><p>沿着林间的小路，找到一处停留的地方。<br/>带上你的数字分身，开始探索世界。</p><div className="town-actions"><button type="button" className="play-button" onClick={onLaunch} disabled={launching}><span className="play-triangle"/>{launching ? '正在启动…' : '进入森林小镇'}</button><button type="button" className="secondary-button" onClick={() => onNavigate('world')}>了解世界 <span aria-hidden="true">↗</span></button></div><div className="town-footnote"><span>本地游戏 · Windows</span><span>开发中原型</span></div></div>
          <span className="illustration-caption">森林小镇 · 场景概念图</span>
        </article>
        <section className="quick-section" aria-labelledby="quick-title"><div className="section-heading"><h2 id="quick-title">从这里开始</h2><span>让你的世界更像你</span></div><div className="quick-grid">{shortcuts.map((item) => <button type="button" className="quick-card" key={item.page} onClick={() => onNavigate(item.page)}><div className="quick-card-top"><span className="quick-icon"><Icon name={item.icon}/></span><span className="quick-tag">{item.tag}</span><span className="quick-arrow" aria-hidden="true">↗</span></div><h3>{item.title}</h3><p>{item.description}</p></button>)}</div></section>
        <footer className="home-footer"><span><i aria-hidden="true"/>人格档案{user.aiAgent.status === 'READY' ? '已创建' : '待初始化'} · {user.basicQuestionnaire?.mbti || '尚未填写性格'}</span><button type="button" onClick={() => onNavigate('profile')}>完善个人档案 <span aria-hidden="true">→</span></button><span className="companion-hint">右上角 ◇ 可切换伴生模式</span></footer>
      </div>
    </section>
  );
}
