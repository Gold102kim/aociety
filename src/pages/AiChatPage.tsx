import { FormEvent, useEffect, useRef, useState } from 'react';
import { LauncherUser } from '../auth';
import { ChatMessage, getAiStatus, sendAiMessage } from '../ai';

type ConnectionState = 'unconfigured' | 'untested' | 'connected' | 'failed';
type AiStatus = { configured: boolean; model: string; connection: ConnectionState; message?: string };

export function AiChatPage({ user, onBack }: { user: LauncherUser; onBack: () => void }) {
  const welcomeMessage: ChatMessage = { id: 'welcome', role: 'assistant', content: `你好，${user.displayName}。我已经准备好了。我们可以从现在开始聊天，想聊什么都可以。` };
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<AiStatus>({ configured: false, model: user.aiAgent.modelAssignment.baseModelId, connection: 'unconfigured' });
  const requestEpoch = useRef(0);

  useEffect(() => {
    let active = true;
    if (window.launcher?.ai) {
      void getAiStatus()
        .then((result) => { if (active) setStatus(result); })
        .catch(() => { if (active) setStatus({ configured: false, model: user.aiAgent.modelAssignment.baseModelId, connection: 'failed', message: '无法读取模型状态。' }); });
    }
    return () => {
      active = false;
      requestEpoch.current += 1;
    };
  }, [user.aiAgent.modelAssignment.baseModelId]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || busy) return;
    const epoch = ++requestEpoch.current;
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content };
    const history = messages.filter((message) => message.id !== 'welcome');
    setMessages((current) => [...current, userMessage]);
    setInput('');
    setError('');
    setBusy(true);
    try {
      const result = await sendAiMessage(content, history);
      if (requestEpoch.current !== epoch) return;
      setMessages((current) => [...current, { id: result.responseId || crypto.randomUUID(), role: 'assistant', content: result.text }]);
      setStatus({ configured: true, model: result.model, connection: 'connected' });
    } catch (submitError) {
      if (requestEpoch.current !== epoch) return;
      setError(submitError instanceof Error ? submitError.message : 'AI 回复生成失败，请稍后重试。');
      if (window.launcher?.ai) void getAiStatus().then((result) => { if (requestEpoch.current === epoch) setStatus(result); }).catch(() => undefined);
    } finally {
      if (requestEpoch.current === epoch) setBusy(false);
    }
  };

  const clearConversation = () => {
    requestEpoch.current += 1;
    setMessages([welcomeMessage]);
    setError('');
    setBusy(false);
  };

  const statusLabel = status.connection === 'connected' ? status.model : status.connection === 'untested' ? '模型配置待验证' : status.connection === 'failed' ? '模型连接失败' : '模型尚未配置';
  const connectionTitle = status.connection === 'connected' ? '共享模型服务已连接' : status.connection === 'untested' ? '模型配置已载入' : status.connection === 'failed' ? '共享模型服务连接失败' : '需要配置 API';
  const connectionDescription = status.connection === 'connected' ? '账户 AI 档案正通过共享模型服务生成回复。' : status.connection === 'untested' ? '配置已找到，发送第一条消息后验证实际连接。' : status.connection === 'failed' ? status.message || '请检查网络、Base URL、模型名称和 API Key。' : '本地模型服务尚未配置，请联系开发人员。';

  return (
    <section className="chat-content">
      <header className="chat-page-header"><div><button type="button" onClick={onBack}>← 返回虚拟分身</button><span>PERSONA CONVERSATION</span><h1>与我的 AI 对话</h1><p>账户专属 AI 档案会通过共享模型服务生成回复。</p></div><span className={`chat-model-status ${status.connection === 'connected' ? 'ready' : ''}`} role="status"><i aria-hidden="true"/>{statusLabel}</span></header>
      <div className="chat-layout">
        <article className="chat-window">
          <div className="chat-agent-bar"><span className="chat-agent-avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><div><strong>{user.displayName} 的数字分身</strong><small>Agent {user.aiAgent.agentId.slice(0, 8)} · 人格档案已就绪</small></div><button type="button" disabled={busy} title={busy ? '等待当前回复完成后再清空' : undefined} onClick={clearConversation}>清空本次对话</button></div>
          <div className="chat-messages" role="log" aria-live="polite" aria-relevant="additions" aria-busy={busy}>
            {messages.map((message) => <div key={message.id} className={`chat-message ${message.role}`}><span>{message.role === 'assistant' ? user.displayName.slice(0, 1).toUpperCase() : '你'}</span><div><small>{message.role === 'assistant' ? '数字分身' : user.displayName}</small><p>{message.content}</p></div></div>)}
            {busy && <div className="chat-message assistant typing" role="status"><span>{user.displayName.slice(0, 1).toUpperCase()}</span><div><small>数字分身</small><p aria-label="正在生成回复"><i/><i/><i/></p></div></div>}
          </div>
          {error && <div className="chat-error" role="alert" aria-live="assertive">{error}</div>}
          <form className="chat-composer" onSubmit={submit}><textarea aria-label="发送给数字分身的消息" value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入你想对分身说的话…" maxLength={2000}/><div><span>{input.length} / 2000</span><button disabled={busy || !input.trim()}>{busy ? '等待回复…' : '发送消息'}</button></div></form>
        </article>
        <aside className="chat-side-column">
          <article className="chat-side-card"><span>PERSONA</span><h2>本次人格依据</h2><dl><div><dt>MBTI</dt><dd>{user.aiAgent.personality.mbti || '未填写'}</dd></div><div><dt>职业</dt><dd>{user.aiAgent.identity.occupation || '未填写'}</dd></div><div><dt>兴趣</dt><dd>{user.aiAgent.preferences.interests.join('、') || '未填写'}</dd></div><div><dt>交流方式</dt><dd>自适应</dd></div></dl></article>
          <article className="chat-side-card chat-config-card"><span>MODEL CONNECTION</span><h2>{connectionTitle}</h2><p>{connectionDescription}</p></article>
          <article className="chat-side-card chat-suggestions"><span>CONVERSATION STARTERS</span><h2>可以试着问</h2>{['你会怎样描述我的性格？', '根据我的爱好，你想和我聊什么？', '如果你替我探索世界，会先去哪里？'].map((suggestion) => <button type="button" key={suggestion} onClick={() => setInput(suggestion)}>{suggestion}</button>)}</article>
        </aside>
      </div>
    </section>
  );
}
