import { FormEvent, lazy, Suspense, useEffect, useState } from 'react';
import { BasicQuestionnaire, completeQuestionnaire, LauncherUser, login, register, signOut, supplementProfile } from './auth';
import { ChatMessage, getAiStatus, sendAiMessage } from './ai';
import { colorOptions, getThemeStyle } from './theme';

const AvatarViewport = lazy(() => import('./AvatarViewport').then((module) => ({ default: module.AvatarViewport })));

function AvatarViewportFallback() {
  return <div className="avatar-viewport avatar-viewport-fallback"><div className="avatar-viewport-state"><i/><span>正在准备 3D 分身</span></div></div>;
}

type AuthMode = 'login' | 'register';
type LauncherPage = 'home' | 'world' | 'avatar' | 'chat' | 'social' | 'profile';

const Icon = ({ name }: { name: 'home' | 'world' | 'avatar' | 'friends' | 'settings' | 'download' | 'user' }) => {
  const paths = {
    home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-6h5v6"/></>,
    world: <><circle cx="12" cy="12" r="9"/><path d="M3.5 9h17M3.5 15h17M12 3c2.2 2.4 3.3 5.4 3.3 9S14.2 18.6 12 21M12 3C9.8 5.4 8.7 8.4 8.7 12s1.1 6.6 3.3 9"/></>,
    avatar: <><circle cx="12" cy="7" r="3.2"/><path d="M7.2 20v-3.2c0-3.1 1.6-5.2 4.8-5.2s4.8 2.1 4.8 5.2V20"/><path d="M4 12.5 2.8 15 5 16.4M20 12.5l1.2 2.5-2.2 1.4"/></>,
    friends: <><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3.5 20c.4-4 2.2-6 5.5-6s5.1 2 5.5 6M14 15c3.8-.4 5.8 1.3 6.5 4"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    download: <><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4.5 21c.6-5 3-7.5 7.5-7.5s6.9 2.5 7.5 7.5"/></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
};

function PageTabs<T extends string>({ items, active, onChange }: { items: Array<{ value: T; label: string; badge?: string }>; active: T; onChange: (value: T) => void }) {
  return <nav className="page-tabs" aria-label="页面分类">{items.map((item) => <button key={item.value} className={active === item.value ? 'active' : ''} onClick={() => onChange(item.value)}><span>{item.label}</span>{item.badge && <small>{item.badge}</small>}</button>)}</nav>;
}

function TitleBar({ canEnterCompanion }: { canEnterCompanion: boolean }) {
  return (
    <header className="titlebar">
      <div className="brand-mini"><span className="brand-mark">E</span><span>ECHO<span>VERSE</span></span></div>
      <div className="window-controls">
        {canEnterCompanion && <button className="companion-toggle" aria-label="折叠到伴生模式" title="折叠到伴生模式" onClick={() => { void window.launcher?.window.enterCompanion(); }}>◇</button>}
        <button aria-label="最小化" onClick={() => window.launcher?.window.minimize()}>—</button>
        <button aria-label="最大化" onClick={() => window.launcher?.window.toggleMaximize()}>□</button>
        <button className="close" aria-label="关闭" onClick={() => window.launcher?.window.close()}>×</button>
      </div>
    </header>
  );
}

function CompanionApp() {
  const [state, setState] = useState<{ displayName: string; agentStatus: 'WAITING_FOR_PROFILE' | 'READY'; favoriteColor: string }>({
    displayName: 'Echo',
    agentStatus: 'WAITING_FOR_PROFILE',
    favoriteColor: new URLSearchParams(window.location.search).get('themeColor') || '薄荷绿',
  });

  useEffect(() => {
    document.body.classList.add('companion-mode');
    document.documentElement.classList.add('companion-mode');
    if (window.launcher?.companion) {
      void window.launcher.companion.getState().then(setState).catch(() => undefined);
    }
    return () => {
      document.body.classList.remove('companion-mode');
      document.documentElement.classList.remove('companion-mode');
    };
  }, []);

  return (
    <main className="companion-root" style={getThemeStyle(state.favoriteColor)} title="拖动我移动位置，双击恢复主界面" onDoubleClick={() => window.launcher?.companion.restore()}>
      <div className="companion-actions">
        <button aria-label="恢复主界面" title="恢复主界面" onClick={() => window.launcher?.companion.restore()}>↗</button>
        <button aria-label="退出软件" title="退出软件" onClick={() => window.launcher?.companion.quit()}>×</button>
      </div>
      <div className="companion-name"><i/>{state.displayName} · {state.agentStatus === 'READY' ? '在线' : '初始化中'}</div>
      <section className="companion-avatar" aria-label={`${state.displayName} 的桌面虚拟分身`}>
        <div className="companion-glow"/>
        <Suspense fallback={<AvatarViewportFallback/>}><AvatarViewport variant="companion"/></Suspense>
      </section>
      <div className="companion-shadow"/>
      <p>双击恢复平台</p>
    </main>
  );
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: LauncherUser) => void }) {
  const [mode, setMode] = useState<AuthMode>('login');
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    if (!/^\S+@\S+\.\S+$/.test(email)) return setMessage('请输入有效的邮箱地址。');
    if (password.length < 8) return setMessage('密码至少需要 8 位。');
    if (mode === 'register' && displayName.trim().length < 2) return setMessage('昵称至少需要 2 个字符。');
    if (mode === 'register' && password !== confirmPassword) return setMessage('两次输入的密码不一致。');

    setBusy(true);
    try {
      const user = mode === 'login'
        ? await login(email, password)
        : await register({ displayName, email, password });
      onAuthenticated(user);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-visual">
        <div className="orb orb-one"/><div className="orb orb-two"/><div className="grid-horizon"/>
        <div className="auth-story">
          <div className="eyebrow">YOUR OTHER SELF IS WAITING</div>
          <h1>另一个世界，<br/><span>正在记住你。</span></h1>
          <p>创建你的数字分身。探索、相遇、成长——即使你暂时离开，它的故事也不会停止。</p>
          <div className="story-stats">
            <div><strong>24 / 7</strong><span>持续生长的世界</span></div>
            <div><strong>AI NATIVE</strong><span>真正独立的数字分身</span></div>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <div className="brand-large"><span className="brand-mark">E</span><span>ECHO<span>VERSE</span></span></div>
          <p className="brand-subtitle">DIGITAL LIFE PLATFORM</p>
          <div className="auth-tabs">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setMessage(''); }}>登录</button>
            <button className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setMessage(''); }}>创建账户</button>
          </div>
          <form onSubmit={submit}>
            {mode === 'register' && <label>玩家昵称<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="你希望别人如何称呼你" autoComplete="nickname"/></label>}
            <label>邮箱地址<input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" type="email" autoComplete="email"/></label>
            <label>密码<input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="至少 8 位字符" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'}/></label>
            {mode === 'register' && <label>确认密码<input value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="再次输入密码" type="password" autoComplete="new-password"/></label>}
            {message && <div className="form-message">{message}</div>}
            <button className="primary-button" disabled={busy}>{busy ? '请稍候…' : mode === 'login' ? '进入平台' : '创建账户并继续'}</button>
          </form>
          <p className="legal">继续即表示你同意《用户协议》和《隐私政策》</p>
          <p className="prototype-note">原型阶段：账户数据仅保存在本机，正式版本将接入云端账户服务。</p>
        </div>
      </section>
    </main>
  );
}

const emptyQuestionnaire: BasicQuestionnaire = {
  fullName: '',
  gender: '',
  birthDate: '',
  residence: '',
  occupation: '',
  interests: ['', '', ''],
  mbti: '',
  favoriteColor: '',
  favoriteMusic: '',
  belief: '',
};

const mbtiOptions = ['INTJ', 'INTP', 'ENTJ', 'ENTP', 'INFJ', 'INFP', 'ENFJ', 'ENFP', 'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ', 'ISTP', 'ISFP', 'ESTP', 'ESFP'];

function QuestionnaireScreen({
  user,
  onCompleted,
  onLogout,
}: {
  user: LauncherUser;
  onCompleted: (user: LauncherUser) => void;
  onLogout: () => void;
}) {
  const [form, setForm] = useState<BasicQuestionnaire>(emptyQuestionnaire);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const update = (field: keyof Omit<BasicQuestionnaire, 'interests'>, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const updateInterest = (index: number, value: string) => {
    setForm((current) => ({
      ...current,
      interests: current.interests.map((interest, currentIndex) => currentIndex === index ? value : interest),
    }));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const updatedUser = await completeQuestionnaire(form);
      onCompleted(updatedUser);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '个人资料保存失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="onboarding-shell" style={getThemeStyle(form.favoriteColor)}>
      <aside className="onboarding-intro">
        <div>
          <div className="onboarding-step">ACCOUNT SETUP · 02 / 02</div>
          <h1>旅程，从这里开始。</h1>
          <p>不必急着定义自己。按照此刻的想法，留下你愿意留下的部分。</p>
        </div>
        <div className="onboarding-account">
          <span className="avatar">{user.displayName.slice(0, 1).toUpperCase()}</span>
          <div><strong>{user.displayName}</strong><small>{user.email}</small></div>
        </div>
      </aside>

      <section className="questionnaire-panel">
        <div className="questionnaire-header">
          <div><span>PLAYER PROFILE</span><h2>关于你</h2></div>
          <button type="button" onClick={onLogout}>退出账户</button>
        </div>
        <p className="questionnaire-note">没有标准答案，所有内容均为选填。请确认后再保存：已填写的内容将被锁定，空白项以后仍可补充。</p>

        <form className="questionnaire-form" onSubmit={submit}>
          <div className="form-grid two-columns">
            <label>姓名（或希望记录的称呼）<input value={form.fullName} onChange={(e) => update('fullName', e.target.value)} placeholder="选填" autoComplete="name"/></label>
            <label>性别
              <select value={form.gender} onChange={(e) => update('gender', e.target.value)}>
                <option value="">不填写</option><option value="女性">女性</option><option value="男性">男性</option><option value="非二元">非二元</option><option value="其他/自定义">其他/自定义</option>
              </select>
            </label>
            <label>出生年月日<input value={form.birthDate} onChange={(e) => update('birthDate', e.target.value)} type="date"/></label>
            <label>居住地<input value={form.residence} onChange={(e) => update('residence', e.target.value)} placeholder="国家、城市或地区，选填"/></label>
            <label>职业<input value={form.occupation} onChange={(e) => update('occupation', e.target.value)} placeholder="选填"/></label>
            <label>MBTI
              <select value={form.mbti} onChange={(e) => update('mbti', e.target.value)}>
                <option value="">不确定或不填写</option>{mbtiOptions.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
          </div>

          <fieldset className="interest-fields">
            <legend>核心爱好 <span>最多三个</span></legend>
            <div className="form-grid three-columns">
              {form.interests.map((interest, index) => <input key={index} value={interest} onChange={(e) => updateInterest(index, e.target.value)} placeholder={`爱好 ${index + 1}`}/>)}
            </div>
          </fieldset>

          <div className="form-grid two-columns">
            <fieldset className="color-preference full-column">
              <legend>喜欢的颜色 <span>将作为账户的界面强调色</span></legend>
              <div className="color-options">
                {colorOptions.map((option) => <button key={option.name} type="button" className={form.favoriteColor === option.name ? 'active' : ''} onClick={() => update('favoriteColor', option.name)} aria-pressed={form.favoriteColor === option.name}><i style={{ background: option.hex }}/><span>{option.name}</span></button>)}
              </div>
              <div className="color-preview"><i/><span>{form.favoriteColor ? `当前选择：${form.favoriteColor}` : '当前使用默认薄荷绿，可选择一种个人强调色'}</span>{form.favoriteColor && <button type="button" onClick={() => update('favoriteColor', '')}>恢复默认</button>}</div>
            </fieldset>
            <label>喜欢的音乐类型<input value={form.favoriteMusic} onChange={(e) => update('favoriteMusic', e.target.value)} placeholder="例如：摇滚、爵士、电子音乐"/></label>
            <label className="full-column">信奉的主义或宗教<input value={form.belief} onChange={(e) => update('belief', e.target.value)} placeholder="敏感信息，可完全不填写"/></label>
          </div>

          {message && <div className="form-message">{message}</div>}
          <div className="questionnaire-footer">
            <span>保存后将进入 EchoVerse 主界面</span>
            <button className="primary-button questionnaire-submit" disabled={busy}>{busy ? '正在保存资料…' : '完成个人资料'}</button>
          </div>
        </form>
      </section>
    </main>
  );
}

function formatProfileDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }).format(new Date(value));
}

function ProfilePage({ user, onBack, onLogout, onUserUpdated }: { user: LauncherUser; onBack: () => void; onLogout: () => void; onUserUpdated: (user: LauncherUser) => void }) {
  const profile = user.basicQuestionnaire;
  const valueOrEmpty = (value?: string) => value || '未填写';
  const [section, setSection] = useState<'personal' | 'preferences' | 'ai' | 'security'>('personal');
  const [supplementing, setSupplementing] = useState(false);
  const [supplementBusy, setSupplementBusy] = useState(false);
  const [supplementMessage, setSupplementMessage] = useState('');
  const [supplement, setSupplement] = useState<BasicQuestionnaire>(() => ({ ...emptyQuestionnaire, interests: ['', '', ''] }));
  const missingPersonal = ['fullName', 'gender', 'birthDate', 'residence', 'occupation'].some((field) => !profile?.[field as keyof BasicQuestionnaire]);
  const missingPreferences = ['mbti', 'favoriteColor', 'favoriteMusic', 'belief'].some((field) => !profile?.[field as keyof BasicQuestionnaire]) || (profile?.interests.length ?? 0) < 3;
  const canSupplement = section === 'personal' ? missingPersonal : section === 'preferences' ? missingPreferences : false;
  const remainingInterestSlots = Math.max(0, 3 - (profile?.interests.length ?? 0));
  const updateSupplement = (field: keyof Omit<BasicQuestionnaire, 'interests'>, value: string) => setSupplement((current) => ({ ...current, [field]: value }));
  const updateSupplementInterest = (index: number, value: string) => setSupplement((current) => ({
    ...current,
    interests: current.interests.map((interest, currentIndex) => currentIndex === index ? value : interest),
  }));
  const saveSupplement = async (event: FormEvent) => {
    event.preventDefault();
    setSupplementBusy(true);
    setSupplementMessage('');
    try {
      const updatedUser = await supplementProfile(supplement);
      onUserUpdated(updatedUser);
      setSupplement({ ...emptyQuestionnaire, interests: ['', '', ''] });
      setSupplementing(false);
    } catch (error) {
      setSupplementMessage(error instanceof Error ? error.message : '资料补充失败，请稍后重试。');
    } finally {
      setSupplementBusy(false);
    }
  };

  return (
    <section className="profile-content">
      <header className="profile-hero">
        <button className="profile-back" onClick={onBack}>← 返回首页</button>
        <div className="profile-identity">
          <span className="profile-avatar-large">{user.displayName.slice(0, 1).toUpperCase()}</span>
          <div>
            <div className="profile-eyebrow">PLAYER PROFILE</div>
            <h1>{user.displayName}</h1>
            <p>{user.email}</p>
          </div>
          <span className="profile-status"><i/>账户状态正常</span>
        </div>
      </header>

      <PageTabs active={section} onChange={(nextSection) => { setSection(nextSection); setSupplementing(false); setSupplementMessage(''); }} items={[
        { value: 'personal', label: '个人资料' },
        { value: 'preferences', label: '偏好' },
        { value: 'ai', label: 'AI 档案' },
        { value: 'security', label: '账户安全' },
      ]}/>

      <div className={`profile-layout profile-section-${section}`}>
        <article className="profile-card profile-details-card">
          <div className="profile-card-heading">
            <div><span>{section === 'preferences' ? 'PREFERENCES' : 'ACCOUNT ARCHIVE'}</span><h2>{section === 'preferences' ? '偏好档案' : '玩家基础档案'}</h2></div>
            <div className="profile-card-actions">
              <small>{canSupplement ? '已填写内容保持锁定' : '当前资料已完整锁定'}</small>
              {canSupplement && <button type="button" onClick={() => { setSupplementing((current) => !current); setSupplementMessage(''); }}>{supplementing ? '收起' : '补充空白项'}</button>}
            </div>
          </div>
          {supplementing && canSupplement && <form className="profile-supplement-form" onSubmit={saveSupplement}>
            <div className="profile-supplement-heading"><div><span>PROFILE SUPPLEMENT</span><h3>补充尚未填写的内容</h3></div><p>保存后将不可修改，请确认无误。</p></div>
            <div className="profile-supplement-grid">
              {section === 'personal' && !profile?.fullName && <label>姓名（或希望记录的称呼）<input value={supplement.fullName} onChange={(event) => updateSupplement('fullName', event.target.value)} placeholder="选填"/></label>}
              {section === 'personal' && !profile?.gender && <label>性别<select value={supplement.gender} onChange={(event) => updateSupplement('gender', event.target.value)}><option value="">不填写</option><option value="女性">女性</option><option value="男性">男性</option><option value="非二元">非二元</option><option value="其他/自定义">其他/自定义</option></select></label>}
              {section === 'personal' && !profile?.birthDate && <label>出生年月日<input value={supplement.birthDate} onChange={(event) => updateSupplement('birthDate', event.target.value)} type="date"/></label>}
              {section === 'personal' && !profile?.residence && <label>居住地<input value={supplement.residence} onChange={(event) => updateSupplement('residence', event.target.value)} placeholder="国家、城市或地区，选填"/></label>}
              {section === 'personal' && !profile?.occupation && <label>职业<input value={supplement.occupation} onChange={(event) => updateSupplement('occupation', event.target.value)} placeholder="选填"/></label>}
              {section === 'preferences' && !profile?.mbti && <label>MBTI<select value={supplement.mbti} onChange={(event) => updateSupplement('mbti', event.target.value)}><option value="">不确定或不填写</option>{mbtiOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>}
              {section === 'preferences' && !profile?.favoriteColor && <label>喜欢的颜色<select value={supplement.favoriteColor} onChange={(event) => updateSupplement('favoriteColor', event.target.value)}><option value="">不填写</option>{colorOptions.map((option) => <option key={option.name} value={option.name}>{option.name}</option>)}</select></label>}
              {section === 'preferences' && !profile?.favoriteMusic && <label>喜欢的音乐类型<input value={supplement.favoriteMusic} onChange={(event) => updateSupplement('favoriteMusic', event.target.value)} placeholder="选填"/></label>}
              {section === 'preferences' && !profile?.belief && <label>信奉的主义或宗教<input value={supplement.belief} onChange={(event) => updateSupplement('belief', event.target.value)} placeholder="敏感信息，可完全不填写"/></label>}
              {section === 'preferences' && remainingInterestSlots > 0 && <fieldset className="profile-supplement-interests"><legend>补充核心爱好 <span>还可填写 {remainingInterestSlots} 个</span></legend><div>{Array.from({ length: remainingInterestSlots }, (_, index) => <input key={index} value={supplement.interests[index]} onChange={(event) => updateSupplementInterest(index, event.target.value)} placeholder={`爱好 ${(profile?.interests.length ?? 0) + index + 1}`}/>)}</div></fieldset>}
            </div>
            {supplementMessage && <div className="form-message">{supplementMessage}</div>}
            <div className="profile-supplement-footer"><span>空白内容可以以后继续补充</span><button className="primary-button" disabled={supplementBusy}>{supplementBusy ? '正在保存…' : '确认并锁定'}</button></div>
          </form>}
          <div className="profile-definition-grid">
            <div className="personal-field"><span>姓名或称呼</span><strong>{valueOrEmpty(profile?.fullName)}</strong></div>
            <div className="personal-field"><span>性别</span><strong>{valueOrEmpty(profile?.gender)}</strong></div>
            <div className="personal-field"><span>出生年月日</span><strong>{valueOrEmpty(profile?.birthDate)}</strong></div>
            <div className="personal-field"><span>居住地</span><strong>{valueOrEmpty(profile?.residence)}</strong></div>
            <div className="personal-field"><span>职业</span><strong>{valueOrEmpty(profile?.occupation)}</strong></div>
            <div className="preference-field"><span>MBTI</span><strong>{valueOrEmpty(profile?.mbti)}</strong></div>
            <div className="preference-field"><span>喜欢的颜色</span><strong>{valueOrEmpty(profile?.favoriteColor)}</strong></div>
            <div className="preference-field"><span>音乐类型</span><strong>{valueOrEmpty(profile?.favoriteMusic)}</strong></div>
            <div className="profile-definition-wide preference-field"><span>信奉的主义或宗教</span><strong>{valueOrEmpty(profile?.belief)}</strong></div>
          </div>
          <div className="profile-interests preference-field">
            <span>核心爱好</span>
            <div>{profile?.interests?.length ? profile.interests.map((interest) => <i key={interest}>{interest}</i>) : <em>未填写</em>}</div>
          </div>
        </article>

        <aside className="profile-side-column">
          <article className="profile-card account-card">
            <div className="profile-card-heading compact"><div><span>{section === 'ai' ? 'AI ARCHIVE' : section === 'security' ? 'SECURITY' : 'ACCOUNT'}</span><h2>{section === 'ai' ? 'AI 档案' : section === 'security' ? '账户安全' : '账户信息'}</h2></div></div>
            <dl>
              <div className="account-field"><dt>玩家昵称</dt><dd>{user.displayName}</dd></div>
              <div className="security-field"><dt>邮箱地址</dt><dd>{user.email}</dd></div>
              <div className="account-field"><dt>注册日期</dt><dd>{formatProfileDate(user.createdAt)}</dd></div>
              <div className="security-field"><dt>账户 ID</dt><dd className="account-id">{user.id}</dd></div>
              <div className="ai-field"><dt>专属 AI 状态</dt><dd>{user.aiAgent.status === 'READY' ? '档案已就绪' : '等待个人资料'}</dd></div>
              <div className="ai-field"><dt>AI Agent ID</dt><dd className="account-id">{user.aiAgent.agentId}</dd></div>
            </dl>
          </article>

          <article className="profile-card logout-card">
            <div className="logout-icon"><Icon name="user"/></div>
            <div><h3>退出当前账户</h3><p>退出后将返回登录界面。你的个人资料和账户信息会继续保存在本机。</p></div>
            <button className="logout-button" onClick={onLogout}>退出登录</button>
          </article>
        </aside>
      </div>
    </section>
  );
}

function WorldPage({ user, onLaunch }: { user: LauncherUser; onLaunch: () => void }) {
  const [section, setSection] = useState<'map' | 'events' | 'travel'>('map');
  const regions = [
    { name: '中央小镇', type: '核心社交区域', status: '原型开发中', className: 'central' },
    { name: '霓虹街区', type: '夜间娱乐区域', status: '尚未开放', className: 'neon' },
    { name: '海滨区域', type: '休闲与资源区域', status: '尚未开放', className: 'coast' },
    { name: '失物招领咖啡馆', type: '情绪主题地点', status: '概念阶段', className: 'cafe' },
  ];

  return (
    <section className={`world-content world-section-${section}`}>
      <header className="world-page-header">
        <div><span>WORLD EXPLORER</span><h1>EchoVerse 世界</h1><p>查看世界状态、主题区域、公共事件以及虚拟分身的探索记录。</p></div>
        <span className="world-server-state demo"><i/>本地世界预览 · 模拟数据</span>
      </header>

      <PageTabs active={section} onChange={setSection} items={[
        { value: 'map', label: '区域地图' },
        { value: 'events', label: '世界事件', badge: '3' },
        { value: 'travel', label: '旅行记录', badge: '2' },
      ]}/>

      <section className="world-metrics">
        <article><span>当前阶段</span><strong>PRE-ALPHA</strong><small>世界原型构建中</small></article>
        <article><span>可预览区域</span><strong>1 / 4</strong><small>中央小镇概念预览</small></article>
        <article><span>模拟居民</span><strong>128</strong><small>用于界面氛围展示</small></article>
        <article><span>世界时间</span><strong>18:42</strong><small>本地演示昼夜周期</small></article>
      </section>

      <div className="world-layout">
        <article className="world-map-card">
          <div className="world-panel-heading"><div><span>REGION MAP</span><h2>世界区域地图</h2></div><small>概念布局 · 非实际比例</small></div>
          <div className="world-map">
            <div className="world-map-grid"/>
            <div className="world-route route-one"/><div className="world-route route-two"/><div className="world-route route-three"/>
            <button className="world-node node-central"><i/><strong>中央小镇</strong><span>核心区域</span></button>
            <button className="world-node node-neon"><i/><strong>霓虹街区</strong><span>夜间区域</span></button>
            <button className="world-node node-coast"><i/><strong>海滨区域</strong><span>休闲区域</span></button>
            <button className="world-node node-cafe"><i/><strong>咖啡馆</strong><span>情绪锚点</span></button>
            <div className="world-map-legend"><span><i/>规划区域</span><span><i/>未开放</span></div>
          </div>
          <div className="world-map-footer"><div><span>下一目标</span><strong>完成中央小镇可行走原型</strong></div><button className="play-button" onClick={onLaunch}><span className="play-triangle"/>进入游戏世界</button></div>
        </article>

        <aside className="world-side-column">
          <article className="world-panel world-event-card">
            <div className="world-panel-heading compact"><div><span>WORLD EVENTS</span><h2>世界事件</h2></div><small>原型模拟</small></div>
            <div className="world-event-list">
              <article><i className="mint">◇</i><div><strong>暮色灯光测试</strong><p>中央小镇正在切换黄昏照明方案。</p></div><time>18:40</time></article>
              <article><i className="amber">△</i><div><strong>流动商店抵达</strong><p>概念商队停留在东侧广场。</p></div><time>17:25</time></article>
              <article><i className="blue">○</i><div><strong>海风数据异常</strong><p>海滨区域环境参数等待校准。</p></div><time>16:08</time></article>
            </div>
          </article>
          <article className="world-panel world-travel-card">
            <div className="world-panel-heading compact"><div><span>TRAVEL LOG</span><h2>分身旅行记录</h2></div><small>演示记录</small></div>
            <div className="world-travel-list">
              <article><span className="world-travel-avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><div><strong>经过中央广场</strong><p>“这里的钟声似乎比记忆中慢了一拍。”</p><small>中央小镇 · 12 分钟前</small></div></article>
              <article><span className="world-travel-marker">⌁</span><div><strong>发现未命名小巷</strong><p>记录了一处带有蓝色灯牌的封闭入口。</p><small>霓虹街区边缘 · 36 分钟前</small></div></article>
            </div>
          </article>
        </aside>
      </div>

      <section className="world-region-section">
        <div className="world-region-heading"><div><span>PLANNED DISTRICTS</span><h2>主题区域</h2></div><p>每个区域会通过场景属性吸引不同性格和兴趣的 AI 分身。</p></div>
        <div className="world-region-grid">
          {regions.map((region, index) => <article key={region.name} className={`world-region-card ${region.className}`}><span>0{index + 1}</span><div><h3>{region.name}</h3><p>{region.type}</p></div><small>{region.status}</small></article>)}
        </div>
      </section>
    </section>
  );
}

function AvatarPage({
  user,
  launching,
  onLaunch,
  onChat,
}: {
  user: LauncherUser;
  launching: boolean;
  onLaunch: () => void;
  onChat: () => void;
}) {
  const profile = user.basicQuestionnaire;
  const interests = profile?.interests.filter(Boolean) ?? [];
  const [section, setSection] = useState<'appearance' | 'personality' | 'roadmap' | 'chat'>('appearance');

  return (
    <section className={`avatar-content avatar-section-${section}`}>
      <header className="avatar-page-header">
        <div><span>DIGITAL AVATAR</span><h1>我的虚拟分身</h1><p>查看分身状态、个性来源和当前使用的外观形象。</p></div>
        <span className="avatar-state-badge temporary"><i/>临时形象已启用</span>
      </header>

      <PageTabs active={section} onChange={(value) => value === 'chat' ? onChat() : setSection(value)} items={[
        { value: 'appearance', label: '外观' },
        { value: 'personality', label: '人格' },
        { value: 'roadmap', label: '分身档案' },
        { value: 'chat', label: 'AI 对话' },
      ]}/>

      <div className="avatar-page-layout">
        <article className="avatar-preview-card">
          <div className="avatar-preview-toolbar"><span>3D AVATAR PREVIEW</span><small>临时分身形象 · WebGL 实时预览</small></div>
          <div className="avatar-preview-stage">
            <div className="avatar-stage-ring ring-one"/><div className="avatar-stage-ring ring-two"/>
            <Suspense fallback={<AvatarViewportFallback/>}><AvatarViewport variant="preview"/></Suspense>
            <div className="avatar-not-created loaded"><strong>临时形象已载入</strong><span>拖动可旋转查看，滚轮可以调整距离。</span></div>
            <div className="avatar-q-preview"><span>CURRENT FORM</span><div><i>3D</i><small>ecy 临时模型</small></div></div>
          </div>
          <div className="avatar-preview-footer">
            <div><span>临时形象状态</span><strong>已启用</strong></div>
            <div className="avatar-progress loaded"><i/></div>
            <button className="play-button" onClick={onLaunch} disabled={launching}><span className="play-triangle"/>{launching ? '正在启动…' : '进入游戏完善分身'}</button>
          </div>
        </article>

        <aside className="avatar-info-column">
          <article className="avatar-info-card">
            <div className="avatar-info-heading"><span>PERSONALITY SEED</span><h2>性格种子</h2><p>属于你的性格轮廓会随着旅程与互动逐渐丰富。</p></div>
            <dl>
              <div><dt>专属 AI</dt><dd className="agent-ready">{user.aiAgent.status === 'READY' ? '已自动分配' : '等待初始化'}</dd></div>
              <div><dt>基础模型</dt><dd>{user.aiAgent.modelAssignment.baseModelId}</dd></div>
              <div><dt>MBTI</dt><dd>{profile?.mbti || '未填写'}</dd></div>
              <div><dt>职业</dt><dd>{profile?.occupation || '未填写'}</dd></div>
              <div><dt>音乐偏好</dt><dd>{profile?.favoriteMusic || '未填写'}</dd></div>
              <div><dt>颜色偏好</dt><dd>{profile?.favoriteColor || '未填写'}</dd></div>
            </dl>
            <div className="avatar-interest-summary"><span>核心爱好</span><div>{interests.length ? interests.map((interest) => <i key={interest}>{interest}</i>) : <em>未填写</em>}</div></div>
            <button className="avatar-chat-button" onClick={onChat}><Icon name="user"/>与我的 AI 对话</button>
          </article>

          <article className="avatar-info-card avatar-creation-roadmap">
            <div className="avatar-info-heading"><span>CREATION FLOW</span><h2>分身档案</h2></div>
            <ol>
              <li className="current"><i>1</i><div><strong>创建外观</strong><span>体型、面部、发型与装饰</span></div></li>
              <li><i>2</i><div><strong>定义声音</strong><span>音色和说话风格</span></div></li>
              <li><i>3</i><div><strong>行为特征</strong><span>待机习惯和步态</span></div></li>
            </ol>
          </article>
        </aside>
      </div>
    </section>
  );
}

function AiChatPage({ user, onBack }: { user: LauncherUser; onBack: () => void }) {
  type ConnectionState = 'unconfigured' | 'untested' | 'connected' | 'failed';
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'welcome',
    role: 'assistant',
    content: `你好，${user.displayName}。我已经准备好了。我们可以从现在开始聊天，想聊什么都可以。`,
  }]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<{ configured: boolean; model: string; connection: ConnectionState; message?: string }>({ configured: false, model: user.aiAgent.modelAssignment.baseModelId, connection: 'unconfigured' });

  useEffect(() => {
    if (!window.launcher?.ai) return;
    void getAiStatus().then((result) => setStatus(result)).catch(() => setStatus({ configured: false, model: user.aiAgent.modelAssignment.baseModelId, connection: 'failed', message: '无法读取模型状态。' }));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || busy) return;
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content };
    const history = messages.filter((message) => message.id !== 'welcome');
    setMessages((current) => [...current, userMessage]);
    setInput('');
    setError('');
    setBusy(true);
    try {
      const result = await sendAiMessage(content, history);
      setMessages((current) => [...current, { id: result.responseId || crypto.randomUUID(), role: 'assistant', content: result.text }]);
      setStatus({ configured: true, model: result.model, connection: 'connected' });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'AI 回复生成失败，请稍后重试。');
      if (window.launcher?.ai) {
        void getAiStatus().then((result) => setStatus(result)).catch(() => undefined);
      }
    } finally {
      setBusy(false);
    }
  };

  const statusLabel = status.connection === 'connected'
    ? status.model
    : status.connection === 'untested'
      ? '模型配置待验证'
      : status.connection === 'failed'
        ? '模型连接失败'
        : '模型尚未配置';
  const connectionTitle = status.connection === 'connected'
    ? '专属模型已连接'
    : status.connection === 'untested'
      ? '模型配置已载入'
      : status.connection === 'failed'
        ? '专属模型连接失败'
        : '需要配置 API';
  const connectionDescription = status.connection === 'connected'
    ? '已成功收到 DeepSeek 模型回复。'
    : status.connection === 'untested'
      ? '配置已找到，发送第一条消息后验证实际连接。'
      : status.connection === 'failed'
        ? status.message || '请检查网络、Base URL、模型名称和 API Key。'
        : '本地模型服务尚未配置，请联系开发人员。';

  return (
    <section className="chat-content">
      <header className="chat-page-header">
        <div><button onClick={onBack}>← 返回虚拟分身</button><span>PERSONA CONVERSATION</span><h1>与我的 AI 对话</h1><p>当前对话由账户注册时分配的专属模型提供支持。</p></div>
        <span className={`chat-model-status ${status.connection === 'connected' ? 'ready' : ''}`}><i/>{statusLabel}</span>
      </header>

      <div className="chat-layout">
        <article className="chat-window">
          <div className="chat-agent-bar">
            <span className="chat-agent-avatar">{user.displayName.slice(0, 1).toUpperCase()}</span>
            <div><strong>{user.displayName} 的数字分身</strong><small>Agent {user.aiAgent.agentId.slice(0, 8)} · 人格档案已就绪</small></div>
            <button onClick={() => { setMessages((current) => current.slice(0, 1)); setError(''); }}>清空本次对话</button>
          </div>
          <div className="chat-messages">
            {messages.map((message) => <div key={message.id} className={`chat-message ${message.role}`}>
              <span>{message.role === 'assistant' ? user.displayName.slice(0, 1).toUpperCase() : '你'}</span>
              <div><small>{message.role === 'assistant' ? '数字分身' : user.displayName}</small><p>{message.content}</p></div>
            </div>)}
            {busy && <div className="chat-message assistant typing"><span>{user.displayName.slice(0, 1).toUpperCase()}</span><div><small>数字分身</small><p><i/><i/><i/></p></div></div>}
          </div>
          {error && <div className="chat-error">{error}</div>}
          <form className="chat-composer" onSubmit={submit}>
            <textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入你想对分身说的话…" maxLength={2000}/>
            <div><span>{input.length} / 2000</span><button disabled={busy || !input.trim()}>{busy ? '等待回复…' : '发送消息'}</button></div>
          </form>
        </article>

        <aside className="chat-side-column">
          <article className="chat-side-card"><span>PERSONA</span><h2>本次人格依据</h2><dl><div><dt>MBTI</dt><dd>{user.aiAgent.personality.mbti || '未填写'}</dd></div><div><dt>职业</dt><dd>{user.aiAgent.identity.occupation || '未填写'}</dd></div><div><dt>兴趣</dt><dd>{user.aiAgent.preferences.interests.join('、') || '未填写'}</dd></div><div><dt>交流方式</dt><dd>自适应</dd></div></dl></article>
          <article className="chat-side-card chat-config-card"><span>MODEL CONNECTION</span><h2>{connectionTitle}</h2><p>{connectionDescription}</p></article>
          <article className="chat-side-card chat-suggestions"><span>CONVERSATION STARTERS</span><h2>可以试着问</h2>{['你会怎样描述我的性格？', '根据我的爱好，你想和我聊什么？', '如果你替我探索世界，会先去哪里？'].map((suggestion) => <button key={suggestion} onClick={() => setInput(suggestion)}>{suggestion}</button>)}</article>
        </aside>
      </div>
    </section>
  );
}

function SocialPage({ user, onLaunch }: { user: LauncherUser; onLaunch: () => void }) {
  const [search, setSearch] = useState('');
  const [searched, setSearched] = useState(false);
  const [section, setSection] = useState<'inbox' | 'friends' | 'discover'>('inbox');
  const interests = user.aiAgent.preferences.interests.filter(Boolean);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setSearched(Boolean(search.trim()));
  };

  return (
    <section className={`social-content social-section-${section}`}>
      <header className="social-page-header">
        <div><span>SOCIAL NETWORK</span><h1>社交中心</h1><p>管理好友、查看分身带回的社交线索，并决定哪些关系值得继续。</p></div>
        <span className="social-connection"><i/>社交原型 · 模拟内容</span>
      </header>

      <PageTabs active={section} onChange={setSection} items={[
        { value: 'inbox', label: '消息', badge: '3' },
        { value: 'friends', label: '好友', badge: '3' },
        { value: 'discover', label: '探索玩家' },
      ]}/>

      <section className="social-metrics">
        <article><span>演示好友</span><strong>3</strong><small>原型界面模拟关系</small></article>
        <article><span>待处理请求</span><strong>1</strong><small>模拟好友申请</small></article>
        <article><span>AI 社交线索</span><strong>4</strong><small>模拟分身探索成果</small></article>
        <article><span>在线好友</span><strong>2</strong><small>非真实在线状态</small></article>
      </section>

      <div className="social-layout">
        <article className="social-panel social-inbox">
          <div className="social-panel-heading">
            <div><span>SOCIAL INBOX</span><h2>社交收件箱</h2></div>
            <small>最近活动</small>
          </div>
          <div className="social-feed">
            <article><span className="social-feed-avatar violet">N</span><div><div><strong>Nova_07 发来好友申请</strong><time>5 分钟前</time></div><p>你们都关注“科幻”和“探索”。分身曾在中央广场短暂交谈。</p><small>模拟请求 · 等待玩家确认</small></div></article>
            <article><span className="social-feed-avatar cyan">L</span><div><div><strong>来自 Lumen 的相遇线索</strong><time>22 分钟前</time></div><p>谈到了电子音乐、夜间城市和一间尚未开放的咖啡馆。</p><small>AI 摘要 · 原型内容</small></div></article>
            <article><span className="social-feed-avatar gold">R</span><div><div><strong>Rin 正在探索海滨区域</strong><time>1 小时前</time></div><p>演示好友状态：可能正在寻找可以共同完成的环境任务。</p><small>好友动态 · 模拟状态</small></div></article>
          </div>
          <div className="social-inbox-footer"><span>AI 不会自动替你建立正式好友关系</span><strong>所有关系均由玩家确认</strong></div>
        </article>

        <aside className="social-side-column">
          <article className="social-panel social-search-card">
            <div className="social-panel-heading compact"><div><span>PLAYER SEARCH</span><h2>查找玩家</h2></div></div>
            <form onSubmit={submitSearch}>
              <input value={search} onChange={(event) => { setSearch(event.target.value); setSearched(false); }} placeholder="输入玩家昵称或账户 ID"/>
              <button>搜索</button>
            </form>
            {searched
              ? <p className="social-search-result">当前原型尚未连接在线玩家目录，暂时无法搜索“{search.trim()}”。</p>
              : <p>正式版本将通过玩家昵称或账户 ID 查找用户，不会公开你未选择公开的个人资料。</p>}
          </article>

          <article className="social-panel friend-list-card">
            <div className="social-panel-heading compact"><div><span>FRIENDS</span><h2>好友列表</h2></div><small>演示 3 人</small></div>
            <div className="friend-preview-list">
              <article><span className="violet">N</span><div><strong>Nova_07</strong><small><i/>在线 · 中央小镇</small></div><button>···</button></article>
              <article><span className="cyan">L</span><div><strong>Lumen</strong><small><i/>在线 · 伴生模式</small></div><button>···</button></article>
              <article className="offline"><span className="gold">R</span><div><strong>Rin</strong><small><i/>2 小时前在线</small></div><button>···</button></article>
            </div>
          </article>
        </aside>
      </div>

      <article className="social-panel social-preference-card">
        <div><span>MATCHING SIGNALS</span><h2>当前社交兴趣信号</h2><p>这些信息来自你的身份偏好，只用于未来生成相遇建议，不会直接建立关系。</p></div>
        <div className="social-interest-tags">{interests.length ? interests.map((interest) => <i key={interest}>{interest}</i>) : <em>尚未填写核心爱好</em>}</div>
        <div className="social-agent-state"><span>专属 AI</span><strong>{user.aiAgent.status === 'READY' ? '档案已就绪' : '等待初始化'}</strong></div>
      </article>
    </section>
  );
}

function LauncherHome({ user, onLogout, onUserUpdated }: { user: LauncherUser; onLogout: () => void; onUserUpdated: (user: LauncherUser) => void }) {
  const [page, setPage] = useState<LauncherPage>(() => {
    const preview = new URLSearchParams(window.location.search).get('preview');
    return import.meta.env.DEV && (preview === 'world' || preview === 'avatar' || preview === 'chat' || preview === 'social' || preview === 'profile') ? preview : 'home';
  });
  const [launchState, setLaunchState] = useState<'idle' | 'launching'>('idle');
  const [toast, setToast] = useState('');
  const [version, setVersion] = useState('0.1.0');

  useEffect(() => { void window.launcher?.app.getVersion().then(setVersion); }, []);

  const launchGame = async () => {
    setLaunchState('launching');
    const result = window.launcher
      ? await window.launcher.game.launch()
      : { ok: false, message: '浏览器预览模式无法启动本地游戏。' };
    setLaunchState('idle');
    setToast(result.message);
    window.setTimeout(() => setToast(''), 5000);
  };

  return (
    <main className="launcher-shell">
      <aside className="sidebar">
        <nav>
          <button className={`nav-item ${page === 'home' ? 'active' : ''}`} onClick={() => setPage('home')}><Icon name="home"/><span>首页</span></button>
          <button className={`nav-item ${page === 'world' ? 'active' : ''}`} onClick={() => setPage('world')}><Icon name="world"/><span>世界</span></button>
          <button className={`nav-item ${page === 'avatar' || page === 'chat' ? 'active' : ''}`} onClick={() => setPage('avatar')}><Icon name="avatar"/><span>虚拟分身</span></button>
          <button className={`nav-item ${page === 'social' ? 'active' : ''}`} onClick={() => setPage('social')}><Icon name="friends"/><span>社交</span></button>
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item"><Icon name="download"/><span>下载管理</span></button>
          <button className="nav-item"><Icon name="settings"/><span>设置</span></button>
          <button className={`profile ${page === 'profile' ? 'active' : ''}`} onClick={() => setPage('profile')} title="打开个人主页">
            <span className="avatar">{user.displayName.slice(0, 1).toUpperCase()}</span>
            <span className="profile-copy"><strong>{user.displayName}</strong><small>在线 · 查看个人主页</small></span>
            <span className="profile-chevron">›</span>
          </button>
        </div>
      </aside>

      {page === 'profile'
        ? <ProfilePage user={user} onBack={() => setPage('home')} onLogout={onLogout} onUserUpdated={onUserUpdated}/>
        : page === 'world'
          ? <WorldPage user={user} onLaunch={() => { void launchGame(); }}/>
        : page === 'avatar'
          ? <AvatarPage user={user} launching={launchState === 'launching'} onLaunch={() => { void launchGame(); }} onChat={() => setPage('chat')}/>
          : page === 'chat'
            ? <AiChatPage user={user} onBack={() => setPage('avatar')}/>
          : page === 'social'
            ? <SocialPage user={user} onLaunch={() => { void launchGame(); }}/>
          : <section className="home-content">
        <div className="hero-game">
          <div className="hero-noise"/><div className="planet"/><div className="silhouette"/>
          <div className="hero-copy">
            <div className="status-pill"><span/> PRE-ALPHA EXPERIENCE</div>
            <h1>ECHO<span>VERSE</span></h1>
            <p className="hero-cn">在世界的另一边，成为另一个你。</p>
            <p className="hero-description">你的数字分身正在等待第一次苏醒。创建性格、探索小镇，并让每一次相遇成为只属于你的故事。</p>
            <div className="hero-actions">
              <button className="play-button" onClick={launchGame} disabled={launchState === 'launching'}><span className="play-triangle"/>{launchState === 'launching' ? '正在启动…' : '启动游戏'}</button>
              <button className="secondary-button">查看详情</button>
            </div>
            <div className="game-meta"><span>版本 {version}</span><span>Windows</span><span>简体中文</span></div>
          </div>
        </div>

        <section className="dashboard-row">
          <article className="news-card featured"><div className="card-tag">开发日志</div><div><h3>世界正在形成</h3><p>首个主题街区、数字分身系统与离线观察模式进入原型阶段。</p><span>阅读开发进度 →</span></div></article>
          <article className="news-card community"><div className="card-tag">社区</div><div><h3>成为世界的第一批居民</h3><p>关注测试资格、开发者活动与共创计划。</p><span>了解更多 →</span></div></article>
          <article className="activity-card"><div className="activity-head"><h3>分身动态</h3><span>原型模拟</span></div><div className="home-activity-feed"><div><i/><p><strong>人格档案保持在线</strong><span>AI Agent 已准备接收新的经历。</span></p><time>刚刚</time></div><div><i/><p><strong>中央小镇传来微弱信号</strong><span>发现一条尚未解锁的探索路线。</span></p><time>12m</time></div><div><i/><p><strong>伴生模式可以使用</strong><span>点击右上角菱形按钮召唤桌宠。</span></p><time>系统</time></div></div></article>
        </section>
      </section>}
      {toast && <div className="toast">{toast}</div>}
    </main>
  );
}

function BootSequence({ user, onComplete }: { user: LauncherUser; onComplete: () => void }) {
  const lines = [
    '> ECHOVERSE BOOT PROTOCOL / BUILD 0.1',
    `> 验证居民身份... ${user.displayName}`,
    '> 初始化神经链接...',
    '> 读取性格档案...',
    `> 同步人格代理... ${user.aiAgent.agentId.slice(0, 8)}`,
    '> 连接世界节点...',
    '> ECHOVERSE 接入成功',
  ];
  const [visibleLines, setVisibleLines] = useState(1);

  useEffect(() => {
    const lineTimer = window.setInterval(() => {
      setVisibleLines((current) => {
        if (current >= lines.length) {
          window.clearInterval(lineTimer);
          return current;
        }
        return current + 1;
      });
    }, 260);
    const completeTimer = window.setTimeout(onComplete, 2700);
    return () => {
      window.clearInterval(lineTimer);
      window.clearTimeout(completeTimer);
    };
  }, []);

  const progress = Math.round((visibleLines / lines.length) * 100);
  return (
    <main className={`boot-sequence ${visibleLines === lines.length ? 'complete' : ''}`} style={getThemeStyle(user.basicQuestionnaire?.favoriteColor)} aria-live="polite">
      <div className="boot-scanline"/>
      <section className="boot-terminal">
        <div className="boot-terminal-heading"><span>ECHOVERSE // NEURAL GATEWAY</span><i>SECURE CHANNEL</i></div>
        <div className="boot-lines">
          {lines.slice(0, visibleLines).map((line, index) => <p key={line} className={index === lines.length - 1 ? 'success' : ''}>{line}</p>)}
          {visibleLines < lines.length && <span className="boot-cursor">█</span>}
        </div>
        <footer><div><i style={{ width: `${progress}%` }}/></div><span>{progress.toString().padStart(3, '0')}%</span></footer>
      </section>
      <div className="boot-brand">ECHO<span>VERSE</span><small>DIGITAL LIFE SYSTEM</small></div>
    </main>
  );
}

function getDevelopmentPreviewUser(): LauncherUser | null {
  const preview = new URLSearchParams(window.location.search).get('preview');
  if (!import.meta.env.DEV || !['profile', 'world', 'avatar', 'chat', 'social', 'boot', 'questionnaire'].includes(preview ?? '')) return null;
  return {
    id: 'preview-account-id',
    displayName: '102Gold',
    email: 'preview@echoverse.local',
    createdAt: '2026-07-15T00:00:00.000Z',
    basicQuestionnaireCompletedAt: preview === 'questionnaire' ? undefined : '2026-07-15T00:05:00.000Z',
    basicQuestionnaire: {
      fullName: '金哲', gender: '男性', birthDate: '2000-01-01', residence: '上海', occupation: '游戏开发者',
      interests: ['游戏', '音乐', '科幻'], mbti: 'INTJ', favoriteColor: new URLSearchParams(window.location.search).get('themeColor') || '薄荷绿', favoriteMusic: '电子音乐', belief: '',
    },
    aiAgent: {
      agentId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', accountId: 'preview-account-id', status: 'READY', profileVersion: 1,
      createdAt: '2026-07-15T00:00:00.000Z', updatedAt: '2026-07-15T00:05:00.000Z',
      modelAssignment: { baseModelId: 'deepseek-v4-flash', strategy: 'dedicated-account-model', assignedAt: '2026-07-15T00:00:00.000Z' },
      identity: { fullName: '金哲', gender: '男性', birthDate: '2000-01-01', residence: '上海', occupation: '游戏开发者' },
      personality: { mbti: 'INTJ', communicationStyle: 'adaptive', inferredTraits: [] },
      preferences: { interests: ['游戏', '音乐', '科幻'], favoriteColor: new URLSearchParams(window.location.search).get('themeColor') || '薄荷绿', favoriteMusic: '电子音乐', belief: '' },
      memoryNamespace: 'agent:preview:memory', questionnaireCompletedAt: '2026-07-15T00:05:00.000Z',
    },
  };
}

function LauncherApplication() {
  const [user, setUser] = useState<LauncherUser | null>(() => getDevelopmentPreviewUser());
  const [booting, setBooting] = useState(() => import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === 'boot');
  const authenticated = (nextUser: LauncherUser) => {
    setUser(nextUser);
    if (nextUser.basicQuestionnaireCompletedAt) setBooting(true);
  };
  const questionnaireCompleted = (nextUser: LauncherUser) => {
    setUser(nextUser);
    setBooting(true);
  };
  const logout = async () => {
    await signOut();
    setBooting(false);
    setUser(null);
  };
  if (booting && user?.basicQuestionnaireCompletedAt) {
    return <BootSequence user={user} onComplete={() => setBooting(false)}/>;
  }
  let content;
  if (!user) content = <AuthScreen onAuthenticated={authenticated}/>;
  else if (!user.basicQuestionnaireCompletedAt) content = <QuestionnaireScreen user={user} onCompleted={questionnaireCompleted} onLogout={() => { void logout(); }}/>;
  else content = <LauncherHome user={user} onLogout={() => { void logout(); }} onUserUpdated={setUser}/>;
  return <div className="app" style={getThemeStyle(user?.basicQuestionnaire?.favoriteColor)}><TitleBar canEnterCompanion={Boolean(user?.basicQuestionnaireCompletedAt)}/>{content}</div>;
}

export default function App() {
  const companionMode = new URLSearchParams(window.location.search).get('mode') === 'companion';
  return companionMode ? <CompanionApp/> : <LauncherApplication/>;
}
