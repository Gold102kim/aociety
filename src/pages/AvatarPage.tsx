import { useState } from 'react';
import { LauncherUser } from '../auth';
import { AvatarScene } from '../components/AvatarScene';
import { Icon, PageTabs } from '../components/LauncherUi';

export function AvatarPage({ user, launching, onLaunch, onChat }: { user: LauncherUser; launching: boolean; onLaunch: () => void; onChat: () => void }) {
  const profile = user.basicQuestionnaire;
  const interests = profile?.interests.filter(Boolean) ?? [];
  const [section, setSection] = useState<'appearance' | 'personality' | 'roadmap' | 'chat'>('appearance');
  return (
    <section className={`avatar-content avatar-section-${section}`}>
      <header className="avatar-page-header"><div><span>DIGITAL AVATAR</span><h1>我的虚拟分身</h1><p>查看分身状态、个性来源和当前使用的外观形象。</p></div><span className="avatar-state-badge temporary"><i aria-hidden="true"/>临时形象已启用</span></header>
      <PageTabs active={section} onChange={(value) => value === 'chat' ? onChat() : setSection(value)} items={[{ value: 'appearance', label: '外观' }, { value: 'personality', label: '人格' }, { value: 'roadmap', label: '分身档案' }, { value: 'chat', label: 'AI 对话' }]}/>
      <div className="avatar-page-layout">
        <article className="avatar-preview-card">
          <div className="avatar-preview-toolbar"><span>3D AVATAR PREVIEW</span><small>临时分身形象 · WebGL 实时预览</small></div>
          <div className="avatar-preview-stage"><div className="avatar-stage-ring ring-one" aria-hidden="true"/><div className="avatar-stage-ring ring-two" aria-hidden="true"/><AvatarScene variant="preview"/><div className="avatar-not-created loaded"><strong>临时形象已载入</strong><span>拖动可旋转查看，滚轮可以调整距离。</span></div><div className="avatar-q-preview"><span>CURRENT FORM</span><div><i>3D</i><small>ecy 临时模型</small></div></div></div>
          <div className="avatar-preview-footer"><div><span>临时形象状态</span><strong>已启用</strong></div><div className="avatar-progress loaded" aria-hidden="true"><i/></div><button type="button" className="play-button" onClick={onLaunch} disabled={launching}><span className="play-triangle"/>{launching ? '正在启动…' : '进入游戏完善分身'}</button></div>
        </article>

        <aside className="avatar-info-column">
          <article className="avatar-info-card">
            <div className="avatar-info-heading"><span>PERSONALITY SEED</span><h2>性格种子</h2><p>属于你的性格轮廓会随着旅程与互动逐渐丰富。</p></div>
            <dl><div><dt>账户 AI 档案</dt><dd className="agent-ready">{user.aiAgent.status === 'READY' ? '已创建' : '等待初始化'}</dd></div><div><dt>共享模型服务</dt><dd>{user.aiAgent.modelAssignment.baseModelId}</dd></div><div><dt>MBTI</dt><dd>{profile?.mbti || '未填写'}</dd></div><div><dt>职业</dt><dd>{profile?.occupation || '未填写'}</dd></div><div><dt>音乐偏好</dt><dd>{profile?.favoriteMusic || '未填写'}</dd></div><div><dt>颜色偏好</dt><dd>{profile?.favoriteColor || '未填写'}</dd></div></dl>
            <div className="avatar-interest-summary"><span>核心爱好</span><div>{interests.length ? interests.map((interest) => <i key={interest}>{interest}</i>) : <em>未填写</em>}</div></div>
            <button type="button" className="avatar-chat-button" onClick={onChat}><Icon name="user"/>与我的 AI 对话</button>
          </article>
          <article className="avatar-info-card avatar-creation-roadmap"><div className="avatar-info-heading"><span>CREATION FLOW</span><h2>分身档案</h2></div><ol><li className="current"><i>1</i><div><strong>创建外观</strong><span>体型、面部、发型与装饰</span></div></li><li><i>2</i><div><strong>定义声音</strong><span>音色和说话风格</span></div></li><li><i>3</i><div><strong>行为特征</strong><span>待机习惯和步态</span></div></li></ol></article>
        </aside>
      </div>
    </section>
  );
}
