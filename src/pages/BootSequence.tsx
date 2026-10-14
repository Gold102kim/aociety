import { useEffect, useMemo, useState } from 'react';
import { LauncherUser } from '../auth';
import { getThemeStyle } from '../theme';
import { version } from '../../package.json';

export function BootSequence({ user, onComplete, durationMs = 2700 }: { user: LauncherUser; onComplete: () => void; durationMs?: number }) {
  const lines = useMemo(() => [
    `> ECHOVERSE BOOT PROTOCOL / BUILD ${version}`,
    `> 验证居民身份... ${user.displayName}`,
    '> 初始化神经链接...',
    '> 读取性格档案...',
    `> 同步账户 AI 档案... ${user.aiAgent.agentId.slice(0, 8)}`,
    '> 连接世界节点...',
    '> ECHOVERSE 接入成功',
  ], [user.aiAgent.agentId, user.displayName]);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [visibleLines, setVisibleLines] = useState(reduceMotion ? lines.length : 1);

  useEffect(() => {
    if (reduceMotion) {
      const completeTimer = window.setTimeout(onComplete, 350);
      return () => window.clearTimeout(completeTimer);
    }
    const lineTimer = window.setInterval(() => setVisibleLines((current) => {
      if (current >= lines.length) {
        window.clearInterval(lineTimer);
        return current;
      }
      return current + 1;
    }), Math.max(50, Math.floor(durationMs / (lines.length + 2))));
    const completeTimer = window.setTimeout(onComplete, durationMs);
    return () => {
      window.clearInterval(lineTimer);
      window.clearTimeout(completeTimer);
    };
  }, [lines.length, onComplete, reduceMotion, durationMs]);

  const progress = Math.round((visibleLines / lines.length) * 100);
  return (
    <main className={`boot-sequence ${visibleLines === lines.length ? 'complete' : ''}`} style={getThemeStyle(user.basicQuestionnaire?.favoriteColor)} role="status" aria-live="polite" aria-label="正在进入 EchoVerse">
      <div className="boot-scanline" aria-hidden="true"/>
      <section className="boot-terminal">
        <div className="boot-terminal-heading"><span>ECHOVERSE // NEURAL GATEWAY</span><i>SECURE CHANNEL</i></div>
        <div className="boot-lines">{lines.slice(0, visibleLines).map((line, index) => <p key={line} className={index === lines.length - 1 ? 'success' : ''}>{line}</p>)}{visibleLines < lines.length && <span className="boot-cursor" aria-hidden="true">█</span>}</div>
        <footer><div aria-hidden="true"><i style={{ width: `${progress}%` }}/></div><span>{progress.toString().padStart(3, '0')}%</span></footer>
      </section>
      <div className="boot-brand" aria-hidden="true">ECHO<span>VERSE</span><small>DIGITAL LIFE SYSTEM</small></div>
    </main>
  );
}
