import { FormEvent, useState } from 'react';
import { BasicQuestionnaire, LauncherUser, supplementProfile } from '../auth';
import { Icon, PageTabs } from '../components/LauncherUi';
import { emptyQuestionnaire, mbtiOptions } from '../profile';
import { colorOptions } from '../theme';

function formatProfileDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '未知' : new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }).format(date);
}

export function ProfilePage({ user, onBack, onLogout, onUserUpdated }: { user: LauncherUser; onBack: () => void; onLogout: () => void; onUserUpdated: (user: LauncherUser) => void }) {
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
  const updateSupplementInterest = (index: number, value: string) => setSupplement((current) => ({ ...current, interests: current.interests.map((interest, currentIndex) => currentIndex === index ? value : interest) }));

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
        <button type="button" className="profile-back" onClick={onBack}>← 返回首页</button>
        <div className="profile-identity"><span className="profile-avatar-large">{user.displayName.slice(0, 1).toUpperCase()}</span><div><div className="profile-eyebrow">PLAYER PROFILE</div><h1>{user.displayName}</h1><p>{user.email}</p></div><span className="profile-status"><i aria-hidden="true"/>账户状态正常</span></div>
      </header>

      <PageTabs active={section} onChange={(nextSection) => { setSection(nextSection); setSupplementing(false); setSupplementMessage(''); }} items={[{ value: 'personal', label: '个人资料' }, { value: 'preferences', label: '偏好' }, { value: 'ai', label: 'AI 档案' }, { value: 'security', label: '账户安全' }]}/>

      <div className={`profile-layout profile-section-${section}`}>
        <article className="profile-card profile-details-card">
          <div className="profile-card-heading"><div><span>{section === 'preferences' ? 'PREFERENCES' : 'ACCOUNT ARCHIVE'}</span><h2>{section === 'preferences' ? '偏好档案' : '玩家基础档案'}</h2></div><div className="profile-card-actions"><small>{canSupplement ? '已填写内容保持锁定' : '当前资料已完整锁定'}</small>{canSupplement && <button type="button" aria-expanded={supplementing} onClick={() => { setSupplementing((current) => !current); setSupplementMessage(''); }}>{supplementing ? '收起' : '补充空白项'}</button>}</div></div>
          {supplementing && canSupplement && <form className="profile-supplement-form" onSubmit={saveSupplement} aria-busy={supplementBusy}>
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
              {section === 'preferences' && remainingInterestSlots > 0 && <fieldset className="profile-supplement-interests"><legend>补充核心爱好 <span>还可填写 {remainingInterestSlots} 个</span></legend><div>{Array.from({ length: remainingInterestSlots }, (_, index) => <input key={index} aria-label={`核心爱好 ${(profile?.interests.length ?? 0) + index + 1}`} value={supplement.interests[index]} onChange={(event) => updateSupplementInterest(index, event.target.value)} placeholder={`爱好 ${(profile?.interests.length ?? 0) + index + 1}`}/>)}</div></fieldset>}
            </div>
            {supplementMessage && <div className="form-message" role="alert" aria-live="assertive">{supplementMessage}</div>}
            <div className="profile-supplement-footer"><span>空白内容可以以后继续补充</span><button className="primary-button" disabled={supplementBusy}>{supplementBusy ? '正在保存…' : '确认并锁定'}</button></div>
          </form>}
          <div className="profile-definition-grid">
            <div className="personal-field"><span>姓名或称呼</span><strong>{valueOrEmpty(profile?.fullName)}</strong></div><div className="personal-field"><span>性别</span><strong>{valueOrEmpty(profile?.gender)}</strong></div><div className="personal-field"><span>出生年月日</span><strong>{valueOrEmpty(profile?.birthDate)}</strong></div><div className="personal-field"><span>居住地</span><strong>{valueOrEmpty(profile?.residence)}</strong></div><div className="personal-field"><span>职业</span><strong>{valueOrEmpty(profile?.occupation)}</strong></div><div className="preference-field"><span>MBTI</span><strong>{valueOrEmpty(profile?.mbti)}</strong></div><div className="preference-field"><span>喜欢的颜色</span><strong>{valueOrEmpty(profile?.favoriteColor)}</strong></div><div className="preference-field"><span>音乐类型</span><strong>{valueOrEmpty(profile?.favoriteMusic)}</strong></div><div className="profile-definition-wide preference-field"><span>信奉的主义或宗教</span><strong>{valueOrEmpty(profile?.belief)}</strong></div>
          </div>
          <div className="profile-interests preference-field"><span>核心爱好</span><div>{profile?.interests?.length ? profile.interests.map((interest) => <i key={interest}>{interest}</i>) : <em>未填写</em>}</div></div>
        </article>

        <aside className="profile-side-column">
          <article className="profile-card account-card"><div className="profile-card-heading compact"><div><span>{section === 'ai' ? 'AI ARCHIVE' : section === 'security' ? 'SECURITY' : 'ACCOUNT'}</span><h2>{section === 'ai' ? 'AI 档案' : section === 'security' ? '账户安全' : '账户信息'}</h2></div></div><dl><div className="account-field"><dt>玩家昵称</dt><dd>{user.displayName}</dd></div><div className="security-field"><dt>邮箱地址</dt><dd>{user.email}</dd></div><div className="account-field"><dt>注册日期</dt><dd>{formatProfileDate(user.createdAt)}</dd></div><div className="security-field"><dt>账户 ID</dt><dd className="account-id">{user.id}</dd></div><div className="ai-field"><dt>账户 AI 档案</dt><dd>{user.aiAgent.status === 'READY' ? '档案已就绪' : '等待个人资料'}</dd></div><div className="ai-field"><dt>AI Agent ID</dt><dd className="account-id">{user.aiAgent.agentId}</dd></div></dl></article>
          <article className="profile-card logout-card"><div className="logout-icon"><Icon name="user"/></div><div><h3>退出当前账户</h3><p>退出后将返回登录界面。你的个人资料和账户信息会继续保存在本机。</p></div><button type="button" className="logout-button" onClick={onLogout}>退出登录</button></article>
        </aside>
      </div>
    </section>
  );
}
