import { FormEvent, useState } from 'react';
import { BasicQuestionnaire, completeQuestionnaire, LauncherUser, login, register } from '../auth';
import { emptyQuestionnaire, mbtiOptions } from '../profile';
import { colorOptions, getThemeStyle } from '../theme';

type AuthMode = 'login' | 'register';

export function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: LauncherUser) => void }) {
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
      const user = mode === 'login' ? await login(email, password) : await register({ displayName, email, password });
      onAuthenticated(user);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };

  const changeMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setMessage('');
  };

  return (
    <main className="auth-shell">
      <section className="auth-visual" aria-label="EchoVerse 简介">
        <div className="orb orb-one" aria-hidden="true"/><div className="orb orb-two" aria-hidden="true"/><div className="grid-horizon" aria-hidden="true"/>
        <div className="auth-story">
          <div className="eyebrow">YOUR OTHER SELF IS WAITING</div>
          <h1>另一个世界，<br/><span>正在记住你。</span></h1>
          <p>创建你的数字分身。探索、相遇、成长——即使你暂时离开，它的故事也不会停止。</p>
          <div className="story-stats"><div><strong>24 / 7</strong><span>持续生长的世界</span></div><div><strong>AI NATIVE</strong><span>真正独立的数字分身</span></div></div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <div className="brand-large"><span className="brand-mark">E</span><span>ECHO<span>VERSE</span></span></div>
          <p className="brand-subtitle">DIGITAL LIFE PLATFORM</p>
          <div className="auth-tabs" role="tablist" aria-label="账户操作">
            <button type="button" role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'active' : ''} onClick={() => changeMode('login')}>登录</button>
            <button type="button" role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'active' : ''} onClick={() => changeMode('register')}>创建账户</button>
          </div>
          <form onSubmit={submit} aria-busy={busy}>
            {mode === 'register' && <label>玩家昵称<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="你希望别人如何称呼你" autoComplete="nickname"/></label>}
            <label>邮箱地址<input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" type="email" autoComplete="email"/></label>
            <label>密码<input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="至少 8 位字符" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'}/></label>
            {mode === 'register' && <label>确认密码<input value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="再次输入密码" type="password" autoComplete="new-password"/></label>}
            {message && <div className="form-message" role="alert" aria-live="assertive">{message}</div>}
            <button className="primary-button" disabled={busy}>{busy ? '请稍候…' : mode === 'login' ? '进入平台' : '创建账户并继续'}</button>
          </form>
          <p className="legal">继续即表示你同意《用户协议》和《隐私政策》</p>
          <p className="prototype-note">原型阶段：账户数据仅保存在本机，正式版本将接入云端账户服务。</p>
        </div>
      </section>
    </main>
  );
}

export function QuestionnaireScreen({ user, onCompleted, onLogout }: { user: LauncherUser; onCompleted: (user: LauncherUser) => void; onLogout: () => void }) {
  const [form, setForm] = useState<BasicQuestionnaire>(emptyQuestionnaire);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const update = (field: keyof Omit<BasicQuestionnaire, 'interests'>, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const updateInterest = (index: number, value: string) => setForm((current) => ({ ...current, interests: current.interests.map((interest, currentIndex) => currentIndex === index ? value : interest) }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      onCompleted(await completeQuestionnaire(form));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '个人资料保存失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="onboarding-shell" style={getThemeStyle(form.favoriteColor)}>
      <aside className="onboarding-intro">
        <div><div className="onboarding-step">ACCOUNT SETUP · 02 / 02</div><h1>旅程，从这里开始。</h1><p>不必急着定义自己。按照此刻的想法，留下你愿意留下的部分。</p></div>
        <div className="onboarding-account"><span className="avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><div><strong>{user.displayName}</strong><small>{user.email}</small></div></div>
      </aside>

      <section className="questionnaire-panel">
        <div className="questionnaire-header"><div><span>PLAYER PROFILE</span><h2>关于你</h2></div><button type="button" onClick={onLogout}>退出账户</button></div>
        <p className="questionnaire-note">没有标准答案，所有内容均为选填。请确认后再保存：已填写的内容将被锁定，空白项以后仍可补充。</p>
        <form className="questionnaire-form" onSubmit={submit} aria-busy={busy}>
          <div className="form-grid two-columns">
            <label>姓名（或希望记录的称呼）<input value={form.fullName} onChange={(event) => update('fullName', event.target.value)} placeholder="选填" autoComplete="name"/></label>
            <label>性别<select value={form.gender} onChange={(event) => update('gender', event.target.value)}><option value="">不填写</option><option value="女性">女性</option><option value="男性">男性</option><option value="非二元">非二元</option><option value="其他/自定义">其他/自定义</option></select></label>
            <label>出生年月日<input value={form.birthDate} onChange={(event) => update('birthDate', event.target.value)} type="date"/></label>
            <label>居住地<input value={form.residence} onChange={(event) => update('residence', event.target.value)} placeholder="国家、城市或地区，选填"/></label>
            <label>职业<input value={form.occupation} onChange={(event) => update('occupation', event.target.value)} placeholder="选填"/></label>
            <label>MBTI<select value={form.mbti} onChange={(event) => update('mbti', event.target.value)}><option value="">不确定或不填写</option>{mbtiOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
          </div>
          <fieldset className="interest-fields"><legend>核心爱好 <span>最多三个</span></legend><div className="form-grid three-columns">{form.interests.map((interest, index) => <input key={index} aria-label={`核心爱好 ${index + 1}`} value={interest} onChange={(event) => updateInterest(index, event.target.value)} placeholder={`爱好 ${index + 1}`}/>)}</div></fieldset>
          <div className="form-grid two-columns">
            <fieldset className="color-preference full-column"><legend>喜欢的颜色 <span>将作为账户的界面强调色</span></legend><div className="color-options">{colorOptions.map((option) => <button key={option.name} type="button" className={form.favoriteColor === option.name ? 'active' : ''} onClick={() => update('favoriteColor', option.name)} aria-pressed={form.favoriteColor === option.name}><i aria-hidden="true" style={{ background: option.hex }}/><span>{option.name}</span></button>)}</div><div className="color-preview"><i aria-hidden="true"/><span>{form.favoriteColor ? `当前选择：${form.favoriteColor}` : '当前使用默认薄荷绿，可选择一种个人强调色'}</span>{form.favoriteColor && <button type="button" onClick={() => update('favoriteColor', '')}>恢复默认</button>}</div></fieldset>
            <label>喜欢的音乐类型<input value={form.favoriteMusic} onChange={(event) => update('favoriteMusic', event.target.value)} placeholder="例如：摇滚、爵士、电子音乐"/></label>
            <label className="full-column">信奉的主义或宗教<input value={form.belief} onChange={(event) => update('belief', event.target.value)} placeholder="敏感信息，可完全不填写"/></label>
          </div>
          {message && <div className="form-message" role="alert" aria-live="assertive">{message}</div>}
          <div className="questionnaire-footer"><span>保存后将进入 EchoVerse 主界面</span><button className="primary-button questionnaire-submit" disabled={busy}>{busy ? '正在保存资料…' : '完成个人资料'}</button></div>
        </form>
      </section>
    </main>
  );
}
