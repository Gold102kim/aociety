import { ReactNode } from 'react';

export type IconName = 'home' | 'world' | 'avatar' | 'chat' | 'friends' | 'settings' | 'download' | 'user';

export function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    chat: <><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-1 1v-9.5A8.5 8.5 0 0 1 11.5 3h1a8.5 8.5 0 0 1 8.5 8.5Z"/><path d="M7 10h10M7 14h6"/></>,
    home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-6h5v6"/></>,
    world: <><circle cx="12" cy="12" r="9"/><path d="M3.5 9h17M3.5 15h17M12 3c2.2 2.4 3.3 5.4 3.3 9S14.2 18.6 12 21M12 3C9.8 5.4 8.7 8.4 8.7 12s1.1 6.6 3.3 9"/></>,
    avatar: <><circle cx="12" cy="7" r="3.2"/><path d="M7.2 20v-3.2c0-3.1 1.6-5.2 4.8-5.2s4.8 2.1 4.8 5.2V20"/><path d="M4 12.5 2.8 15 5 16.4M20 12.5l1.2 2.5-2.2 1.4"/></>,
    friends: <><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3.5 20c.4-4 2.2-6 5.5-6s5.1 2 5.5 6M14 15c3.8-.4 5.8 1.3 6.5 4"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    download: <><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4.5 21c.6-5 3-7.5 7.5-7.5s6.9 2.5 7.5 7.5"/></>,
  };
  return <svg className="icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

export function PageTabs<T extends string>({ items, active, onChange }: { items: Array<{ value: T; label: string; badge?: string }>; active: T; onChange: (value: T) => void }) {
  return <nav className="page-tabs" aria-label="页面分类">{items.map((item) => <button key={item.value} type="button" className={active === item.value ? 'active' : ''} aria-current={active === item.value ? 'page' : undefined} onClick={() => onChange(item.value)}><span>{item.label}</span>{item.badge && <small>{item.badge}</small>}</button>)}</nav>;
}

export function TitleBar({ canEnterCompanion, reducedTransparency, systemReducedTransparency, onToggleTransparency }: { canEnterCompanion: boolean; reducedTransparency: boolean; systemReducedTransparency: boolean; onToggleTransparency: () => void }) {
  const enterCompanion = () => { void window.launcher?.window.enterCompanion().catch(() => undefined); };
  return (
    <header className="titlebar">
      <div className="brand-mini"><span className="brand-mark">E</span><span>ECHO<span>VERSE</span></span></div>
      <div className="window-controls">
        <button type="button" className="appearance-toggle" aria-label="减少透明效果" aria-pressed={reducedTransparency} disabled={systemReducedTransparency} title={systemReducedTransparency ? '清晰模式由系统辅助功能设置启用' : reducedTransparency ? '切换到玻璃质感' : '切换到清晰模式，减少透明效果'} onClick={onToggleTransparency}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="3" y="3" width="11" height="11" rx="4"/><rect x="7" y="7" width="10" height="10" rx="4"/></svg><span>{systemReducedTransparency ? '清晰 · 系统' : reducedTransparency ? '清晰' : '玻璃'}</span></button>
        {canEnterCompanion && <button type="button" className="companion-toggle" aria-label="折叠到伴生模式" title="折叠到伴生模式" onClick={enterCompanion}>◇</button>}
        <button type="button" aria-label="最小化" onClick={() => window.launcher?.window.minimize()}>—</button>
        <button type="button" aria-label="最大化" onClick={() => window.launcher?.window.toggleMaximize()}>□</button>
        <button type="button" className="close" aria-label="关闭" onClick={() => window.launcher?.window.close()}>×</button>
      </div>
    </header>
  );
}
