import { FormEvent, useEffect, useRef, useState } from 'react';
import { LauncherUser } from '../auth';
import { ChatMessage, getAiStatus, sendAiMessage } from '../ai';
import { getRecentChatHistory, isChatSendShortcut } from '../chatConversation';

type ConnectionState = 'unconfigured' | 'untested' | 'connected' | 'failed';
type AiStatus = { configured: boolean; model: string; connection: ConnectionState; message?: string };
type ChatTurn = { message: ChatMessage; history: ChatMessage[] };

export function AiChatPage({ user, onBack, active = true }: { user: LauncherUser; onBack: () => void; active?: boolean }) {
  const welcomeMessage: ChatMessage = { id: 'welcome', role: 'assistant', content: `你好，${user.displayName}。我已经准备好了。我们可以从现在开始聊天，想聊什么都可以。` };
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [failedTurn, setFailedTurn] = useState<ChatTurn | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [status, setStatus] = useState<AiStatus>({ configured: false, model: user.aiAgent.modelAssignment.baseModelId, connection: 'unconfigured' });
  const requestEpoch = useRef(0);
  const messagesRef = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const inFlight = useRef(false);

  useEffect(() => {
    if (active && followLatest.current && messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [active, messages.length, busy]);

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

  const requestReply = async (turn: ChatTurn) => {
    if (inFlight.current) return;
    inFlight.current = true;
    const epoch = ++requestEpoch.current;
    followLatest.current = true;
    setFailedTurn(null);
    setError('');
    setBusy(true);
    try {
      const result = await sendAiMessage(turn.message.content, turn.history);
      if (requestEpoch.current !== epoch) return;
      setMessages((current) => [...current, { id: result.responseId || crypto.randomUUID(), role: 'assistant', content: result.text }]);
      setStatus({ configured: true, model: result.model, connection: 'connected' });
    } catch (submitError) {
      if (requestEpoch.current !== epoch) return;
      setFailedTurn(turn);
      setError(submitError instanceof Error ? submitError.message : 'AI 回复生成失败，请稍后重试。');
      if (window.launcher?.ai) void getAiStatus().then((result) => { if (requestEpoch.current === epoch) setStatus(result); }).catch(() => undefined);
    } finally {
      inFlight.current = false;
      if (requestEpoch.current === epoch) setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || inFlight.current) return;
    const message: ChatMessage = { id: crypto.randomUUID(), role: 'user', content };
    const turn = { message, history: getRecentChatHistory(messages) };
    setMessages((current) => [...current, message]);
    setConfirmClear(false);
    setInput('');
    void requestReply(turn);
  };

  const clearConversation = () => {
    if (inFlight.current) return;
    followLatest.current = true;
    requestEpoch.current += 1;
    setMessages([welcomeMessage]);
    setError('');
    setFailedTurn(null);
    setBusy(false);
    setConfirmClear(false);
    inputRef.current?.focus();
  };

  const browserPreview = import.meta.env.DEV && !window.launcher?.ai;
  const statusLabel = browserPreview ? '浏览器预览 · 不连接模型' : status.connection === 'connected' ? status.model : status.connection === 'untested' ? '模型配置待验证' : status.connection === 'failed' ? '模型连接失败' : '模型尚未配置';
  const connectionTitle = browserPreview ? '模型在桌面端连接' : status.connection === 'connected' ? '共享模型服务已连接' : status.connection === 'untested' ? '模型配置已载入' : status.connection === 'failed' ? '共享模型服务连接失败' : '需要配置 API';
  const connectionDescription = browserPreview ? '此预览不读取 API 密钥，也不发送模型请求。请在桌面软件中使用 AI 对话。' : status.connection === 'connected' ? '账户 AI 档案正通过共享模型服务生成回复。' : status.connection === 'untested' ? '配置已找到，发送第一条消息后验证实际连接。' : status.connection === 'failed' ? status.message || '请检查网络、Base URL、模型名称和 API Key。' : '本地模型服务尚未配置，请联系开发人员。';

  return (
    <section className="chat-content" hidden={!active}>
      <header className="chat-page-header"><div><button type="button" onClick={onBack}>← 返回虚拟分身</button><span>PERSONA CONVERSATION</span><h1>与我的 AI 对话</h1><p>账户专属 AI 档案会通过共享模型服务生成回复。</p></div><span className={`chat-model-status ${status.connection === 'connected' ? 'ready' : ''}`} role="status"><i aria-hidden="true"/>{statusLabel}</span></header>
      <div className="chat-layout">
        <article className="chat-window">
          <div className="chat-agent-bar"><span className="chat-agent-avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><div><strong>{user.displayName} 的数字分身</strong><small>人格档案已就绪 · 当前会话</small></div><div className="chat-clear-actions">{confirmClear ? <><span role="status">清空后无法恢复</span><button type="button" onClick={() => setConfirmClear(false)}>取消</button><button type="button" className="confirm-clear" disabled={busy} onClick={clearConversation}>确认清空</button></> : <button type="button" disabled={busy || messages.length === 1} title={busy ? '等待当前回复完成后再清空' : undefined} onClick={() => setConfirmClear(true)}>清空本次对话</button>}</div></div>
          <div ref={messagesRef} className="chat-messages" role="log" aria-live="polite" aria-relevant="additions" aria-busy={busy} onScroll={(event) => {
            const pane = event.currentTarget;
            followLatest.current = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 64;
          }}>
            {messages.map((message) => <div key={message.id} className={`chat-message ${message.role}`}><span>{message.role === 'assistant' ? user.displayName.slice(0, 1).toUpperCase() : '你'}</span><div><small>{message.role === 'assistant' ? '数字分身' : user.displayName}</small><p>{message.content}</p></div></div>)}
            {busy && <div className="chat-message assistant typing" role="status"><span>{user.displayName.slice(0, 1).toUpperCase()}</span><div><small>数字分身</small><p aria-label="正在生成回复"><i/><i/><i/></p></div></div>}
          </div>
          {error && <div className="chat-error" role="alert" aria-live="assertive"><span>{error}</span>{failedTurn && <button type="button" disabled={busy} onClick={() => { void requestReply(failedTurn); }}>重试上一条</button>}</div>}
          <form className="chat-composer" onSubmit={submit}><textarea ref={inputRef} aria-label="发送给数字分身的消息" value={input} onChange={(event) => setInput(event.target.value)} placeholder="今天有什么想分享的？" maxLength={2000} onKeyDown={(event) => {
            if (isChatSendShortcut({ key: event.key, ctrlKey: event.ctrlKey, metaKey: event.metaKey, isComposing: event.nativeEvent.isComposing || event.keyCode === 229 })) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}/><div><span>{input.length} / 2000 · Ctrl+Enter 发送</span><button disabled={busy || !input.trim()}>{busy ? '等待回复…' : '发送消息'}</button></div></form>
        </article>
        <aside className="chat-side-column">
          <article className="chat-side-card"><span>PERSONA</span><h2>本次人格依据</h2><dl><div><dt>MBTI</dt><dd>{user.aiAgent.personality.mbti || '未填写'}</dd></div><div><dt>职业</dt><dd>{user.aiAgent.identity.occupation || '未填写'}</dd></div><div><dt>兴趣</dt><dd>{user.aiAgent.preferences.interests.join('、') || '未填写'}</dd></div><div><dt>交流方式</dt><dd>自适应</dd></div></dl></article>
          <article className="chat-side-card chat-config-card"><span>MODEL CONNECTION</span><h2>{connectionTitle}</h2><p>{connectionDescription}</p></article>
          <article className="chat-side-card chat-suggestions"><span>CONVERSATION STARTERS</span><h2>可以试着问</h2>{['你会怎样描述我的性格？', '根据我的爱好，你想和我聊什么？', '如果你替我探索世界，会先去哪里？'].map((suggestion) => <button type="button" key={suggestion} onClick={() => { setInput(suggestion); inputRef.current?.focus(); }}>{suggestion}</button>)}</article>
        </aside>
      </div>
    </section>
  );
}
