import { useState } from 'react';
import { LauncherUser } from '../auth';
import { PageTabs } from '../components/LauncherUi';

const regions = [
  { name: '中央小镇', type: '核心社交区域', status: '原型开发中', className: 'central' },
  { name: '霓虹街区', type: '夜间娱乐区域', status: '尚未开放', className: 'neon' },
  { name: '海滨区域', type: '休闲与资源区域', status: '尚未开放', className: 'coast' },
  { name: '失物招领咖啡馆', type: '情绪主题地点', status: '概念阶段', className: 'cafe' },
];

export function WorldPage({ user, onLaunch }: { user: LauncherUser; onLaunch: () => void }) {
  const [section, setSection] = useState<'map' | 'events' | 'travel'>('map');
  return (
    <section className={`world-content world-section-${section}`}>
      <header className="world-page-header"><div><span>WORLD EXPLORER</span><h1>EchoVerse 世界</h1><p>查看世界状态、主题区域、公共事件以及虚拟分身的探索记录。</p></div><span className="world-server-state demo"><i aria-hidden="true"/>本地世界预览 · 模拟数据</span></header>
      <PageTabs active={section} onChange={setSection} items={[{ value: 'map', label: '区域地图' }, { value: 'events', label: '世界事件', badge: '3' }, { value: 'travel', label: '旅行记录', badge: '2' }]}/>
      <section className="world-metrics" aria-label="世界概况"><article><span>当前阶段</span><strong>PRE-ALPHA</strong><small>世界原型构建中</small></article><article><span>可预览区域</span><strong>1 / 4</strong><small>中央小镇概念预览</small></article><article><span>模拟居民</span><strong>128</strong><small>用于界面氛围展示</small></article><article><span>世界时间</span><strong>18:42</strong><small>本地演示昼夜周期</small></article></section>

      <div className="world-layout">
        <article className="world-map-card">
          <div className="world-panel-heading"><div><span>REGION MAP</span><h2>世界区域地图</h2></div><small>概念布局 · 非实际比例</small></div>
          <div className="world-map"><div className="world-map-grid" aria-hidden="true"/><div className="world-route route-one" aria-hidden="true"/><div className="world-route route-two" aria-hidden="true"/><div className="world-route route-three" aria-hidden="true"/><button type="button" className="world-node node-central"><i/><strong>中央小镇</strong><span>核心区域</span></button><button type="button" className="world-node node-neon"><i/><strong>霓虹街区</strong><span>夜间区域</span></button><button type="button" className="world-node node-coast"><i/><strong>海滨区域</strong><span>休闲区域</span></button><button type="button" className="world-node node-cafe"><i/><strong>咖啡馆</strong><span>情绪锚点</span></button><div className="world-map-legend"><span><i/>规划区域</span><span><i/>未开放</span></div></div>
          <div className="world-map-footer"><div><span>下一目标</span><strong>完成中央小镇可行走原型</strong></div><button type="button" className="play-button" onClick={onLaunch}><span className="play-triangle"/>进入游戏世界</button></div>
        </article>
        <aside className="world-side-column">
          <article className="world-panel world-event-card"><div className="world-panel-heading compact"><div><span>WORLD EVENTS</span><h2>世界事件</h2></div><small>原型模拟</small></div><div className="world-event-list"><article><i className="mint">◇</i><div><strong>暮色灯光测试</strong><p>中央小镇正在切换黄昏照明方案。</p></div><time>18:40</time></article><article><i className="amber">△</i><div><strong>流动商店抵达</strong><p>概念商队停留在东侧广场。</p></div><time>17:25</time></article><article><i className="blue">○</i><div><strong>海风数据异常</strong><p>海滨区域环境参数等待校准。</p></div><time>16:08</time></article></div></article>
          <article className="world-panel world-travel-card"><div className="world-panel-heading compact"><div><span>TRAVEL LOG</span><h2>分身旅行记录</h2></div><small>演示记录</small></div><div className="world-travel-list"><article><span className="world-travel-avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><div><strong>经过中央广场</strong><p>“这里的钟声似乎比记忆中慢了一拍。”</p><small>中央小镇 · 12 分钟前</small></div></article><article><span className="world-travel-marker">⌁</span><div><strong>发现未命名小巷</strong><p>记录了一处带有蓝色灯牌的封闭入口。</p><small>霓虹街区边缘 · 36 分钟前</small></div></article></div></article>
        </aside>
      </div>

      <section className="world-region-section"><div className="world-region-heading"><div><span>PLANNED DISTRICTS</span><h2>主题区域</h2></div><p>每个区域会通过场景属性吸引不同性格和兴趣的 AI 分身。</p></div><div className="world-region-grid">{regions.map((region, index) => <article key={region.name} className={`world-region-card ${region.className}`}><span>0{index + 1}</span><div><h3>{region.name}</h3><p>{region.type}</p></div><small>{region.status}</small></article>)}</div></section>
    </section>
  );
}
