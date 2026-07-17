import { FormEvent, useState } from 'react';
import { LauncherUser } from '../auth';
import { PageTabs } from '../components/LauncherUi';

export function SocialPage({ user }: { user: LauncherUser }) {
  const [search, setSearch] = useState('');
  const [searched, setSearched] = useState(false);
  const [section, setSection] = useState<'inbox' | 'friends' | 'discover'>('inbox');
  const interests = user.aiAgent.preferences.interests.filter(Boolean);
  const submitSearch = (event: FormEvent) => { event.preventDefault(); setSearched(Boolean(search.trim())); };
  return (
    <section className={`social-content social-section-${section}`}>
      <header className="social-page-header"><div><span>SOCIAL NETWORK</span><h1>社交中心</h1><p>管理好友、查看分身带回的社交线索，并决定哪些关系值得继续。</p></div><span className="social-connection"><i aria-hidden="true"/>社交原型 · 模拟内容</span></header>
      <PageTabs active={section} onChange={setSection} items={[{ value: 'inbox', label: '消息', badge: '3' }, { value: 'friends', label: '好友', badge: '3' }, { value: 'discover', label: '探索玩家' }]}/>
      <section className="social-metrics" aria-label="社交概况"><article><span>演示好友</span><strong>3</strong><small>原型界面模拟关系</small></article><article><span>待处理请求</span><strong>1</strong><small>模拟好友申请</small></article><article><span>AI 社交线索</span><strong>4</strong><small>模拟分身探索成果</small></article><article><span>在线好友</span><strong>2</strong><small>非真实在线状态</small></article></section>
      <div className="social-layout">
        <article className="social-panel social-inbox"><div className="social-panel-heading"><div><span>SOCIAL INBOX</span><h2>社交收件箱</h2></div><small>最近活动</small></div><div className="social-feed"><article><span className="social-feed-avatar violet">N</span><div><div><strong>Nova_07 发来好友申请</strong><time>5 分钟前</time></div><p>你们都关注“科幻”和“探索”。分身曾在中央广场短暂交谈。</p><small>模拟请求 · 等待玩家确认</small></div></article><article><span className="social-feed-avatar cyan">L</span><div><div><strong>来自 Lumen 的相遇线索</strong><time>22 分钟前</time></div><p>谈到了电子音乐、夜间城市和一间尚未开放的咖啡馆。</p><small>AI 摘要 · 原型内容</small></div></article><article><span className="social-feed-avatar gold">R</span><div><div><strong>Rin 正在探索海滨区域</strong><time>1 小时前</time></div><p>演示好友状态：可能正在寻找可以共同完成的环境任务。</p><small>好友动态 · 模拟状态</small></div></article></div><div className="social-inbox-footer"><span>AI 不会自动替你建立正式好友关系</span><strong>所有关系均由玩家确认</strong></div></article>
        <aside className="social-side-column">
          <article className="social-panel social-search-card"><div className="social-panel-heading compact"><div><span>PLAYER SEARCH</span><h2>查找玩家</h2></div></div><form onSubmit={submitSearch}><label className="sr-only" htmlFor="player-search">玩家昵称或账户 ID</label><input id="player-search" value={search} onChange={(event) => { setSearch(event.target.value); setSearched(false); }} placeholder="输入玩家昵称或账户 ID"/><button>搜索</button></form>{searched ? <p className="social-search-result" role="status">当前原型尚未连接在线玩家目录，暂时无法搜索“{search.trim()}”。</p> : <p>正式版本将通过玩家昵称或账户 ID 查找用户，不会公开你未选择公开的个人资料。</p>}</article>
          <article className="social-panel friend-list-card"><div className="social-panel-heading compact"><div><span>FRIENDS</span><h2>好友列表</h2></div><small>演示 3 人</small></div><div className="friend-preview-list"><article><span className="violet">N</span><div><strong>Nova_07</strong><small><i/>在线 · 中央小镇</small></div><button type="button" aria-label="Nova_07 的更多操作">···</button></article><article><span className="cyan">L</span><div><strong>Lumen</strong><small><i/>在线 · 伴生模式</small></div><button type="button" aria-label="Lumen 的更多操作">···</button></article><article className="offline"><span className="gold">R</span><div><strong>Rin</strong><small><i/>2 小时前在线</small></div><button type="button" aria-label="Rin 的更多操作">···</button></article></div></article>
        </aside>
      </div>
      <article className="social-panel social-preference-card"><div><span>MATCHING SIGNALS</span><h2>当前社交兴趣信号</h2><p>这些信息来自你的身份偏好，只用于未来生成相遇建议，不会直接建立关系。</p></div><div className="social-interest-tags">{interests.length ? interests.map((interest) => <i key={interest}>{interest}</i>) : <em>尚未填写核心爱好</em>}</div><div className="social-agent-state"><span>账户 AI 档案</span><strong>{user.aiAgent.status === 'READY' ? '已就绪' : '等待初始化'}</strong></div></article>
    </section>
  );
}
