import { useState } from 'react';
import { LauncherUser } from '../auth';
import { AvatarScene, type AvatarLoadStatus } from '../components/AvatarScene';
import { Icon, PageTabs } from '../components/LauncherUi';

export function AvatarPage({ user, launching, onLaunch, onChat }: { user: LauncherUser; launching: boolean; onLaunch: () => void; onChat: () => void }) {
  const profile = user.basicQuestionnaire;
  const interests = profile?.interests.filter(Boolean) ?? [];
  const [section, setSection] = useState<'appearance' | 'personality' | 'roadmap' | 'chat'>('appearance');
  const [avatarStatus, setAvatarStatus] = useState<AvatarLoadStatus>('loading');
  const statusLabel = avatarStatus === 'ready' ? '外观已载入' : avatarStatus === 'error' ? '外观暂不可用' : '正在载入外观';
  return (
    <section className={`avatar-content avatar-section-${section}`}>
      <header className="avatar-page-header"><div><h1>我的虚拟分身</h1><p>先从对话认识彼此。3D 外观是可选展示，不决定数字代表是否可用。</p></div><span className={`avatar-state-badge ${avatarStatus === 'ready' ? 'temporary' : ''}`}><i aria-hidden="true"/>{statusLabel}</span></header>
      <PageTabs active={section} onChange={(value) => value === 'chat' ? onChat() : setSection(value)} items={[{ value: 'appearance', label: '外观' }, { value: 'personality', label: '旧版资料' }, { value: 'roadmap', label: '后续计划' }, { value: 'chat', label: 'AI 对话' }]}/>
      <div className="avatar-page-layout">
        <article className="avatar-preview-card">
          <div className="avatar-preview-toolbar"><span>外观预览</span><small>可选本机模型 · WebGL</small></div>
          <div className="avatar-preview-stage"><div className="avatar-stage-ring ring-one" aria-hidden="true"/><div className="avatar-stage-ring ring-two" aria-hidden="true"/><AvatarScene variant="preview" onStatusChange={setAvatarStatus}/>{avatarStatus === 'ready' && <div className="avatar-not-created loaded"><strong>本机临时外观</strong><span>拖动可旋转查看，滚轮可以调整距离。</span></div>}</div>
          <div className="avatar-preview-footer"><div><span>外观状态</span><strong>{statusLabel}</strong></div><button type="button" className="avatar-chat-button" onClick={onChat}>继续文字对话</button><button type="button" className="avatar-chat-button" onClick={onLaunch} disabled={launching}>{launching ? '正在启动…' : '启动本机游戏（可选）'}</button></div>
        </article>

        <aside className="avatar-info-column">
          <article className="avatar-info-card">
            <div className="avatar-info-heading"><h2>本机旧版资料</h2><p>保留你曾填写的资料；不会自动导入新画像或发送给模型。新记忆请在 AI 对话中管理，无需补填问卷。</p></div>
            <dl><div><dt>旧版问卷</dt><dd>{user.basicQuestionnaireCompletedAt ? '已保留' : '未填写（不影响对话）'}</dd></div><div><dt>模型配置</dt><dd>{user.aiAgent.modelAssignment.baseModelId}</dd></div><div><dt>MBTI</dt><dd>{profile?.mbti || '未填写'}</dd></div><div><dt>职业</dt><dd>{profile?.occupation || '未填写'}</dd></div><div><dt>音乐偏好</dt><dd>{profile?.favoriteMusic || '未填写'}</dd></div><div><dt>颜色偏好</dt><dd>{profile?.favoriteColor || '未填写'}</dd></div></dl>
            <div className="avatar-interest-summary"><span>核心爱好</span><div>{interests.length ? interests.map((interest) => <i key={interest}>{interest}</i>) : <em>未填写</em>}</div></div>
            <button type="button" className="avatar-chat-button" onClick={onChat}><Icon name="user"/>与我的 AI 对话</button>
          </article>
          <article className="avatar-info-card avatar-creation-roadmap"><div className="avatar-info-heading"><h2>后续计划</h2><p>以下能力尚未实现，不是开始对话的前置任务。</p></div><ol><li><i>1</i><div><strong>自定义外观</strong><span>体型、面部、发型与装饰 · 规划中</span></div></li><li><i>2</i><div><strong>定义声音</strong><span>音色和说话风格 · 规划中</span></div></li><li><i>3</i><div><strong>行为特征</strong><span>待机习惯和步态 · 规划中</span></div></li></ol></article>
        </aside>
      </div>
    </section>
  );
}
