import { FormEvent, useEffect, useRef, useState } from 'react';
import { LauncherUser } from '../auth';
import { ChatMessage, getAiStatus, sendAiMessage } from '../ai';
import { getRecentChatHistory, isChatSendShortcut } from '../chatConversation';
import { RepresentativePanel } from '../components/RepresentativePanel';
import { ContinuityPanel } from '../components/ContinuityPanel';
import { PrivateSimulationPanel } from '../components/PrivateSimulationPanel';
import { Icon } from '../components/LauncherUi';
import type { ContinuationAction, RepresentativeAction, RepresentativeResult, RepresentativeState } from '../../electron/representative-types';

type ConnectionState = 'unconfigured' | 'untested' | 'connected' | 'failed';
type AiStatus = { configured: boolean; provider?: 'deepseek' | 'openai'; model: string; connection: ConnectionState; message?: string };
type ChatTurn = { message: ChatMessage; history: ChatMessage[]; savedContent: boolean };

export function AiChatPage({ user, onBack, active = true }: { user: LauncherUser; onBack: () => void; active?: boolean }) {
  const welcomeMessage: ChatMessage = { id: 'welcome', role: 'assistant', content: `你好，${user.displayName}。从一个想法开始，不需要填写问卷。是否记住偏好，由你决定。` };
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
  const [privacy, setPrivacy] = useState<RepresentativeState | null>(null);
  const [privacyBusy, setPrivacyBusy] = useState(false);
  const [privacyError, setPrivacyError] = useState('');
  const [learningNotice, setLearningNotice] = useState('');
  const [continuationError, setContinuationError] = useState('');
  const [continuationNotice, setContinuationNotice] = useState('');
  const [saveRequest, setSaveRequest] = useState<{ id: number; content: string } | null>(null);
  const restoredDraft = useRef(false);
  const [learningPaused, setLearningPaused] = useState(false);
  const [temporary, setTemporary] = useState(false);
  const mounted = useRef(true);
  const privacyInFlight = useRef(false);
  const privacyRead = useRef(0);
  const [workspace, setWorkspace] = useState<'chat' | 'simulation'>('chat');
  const [simulationKey, setSimulationKey] = useState(0);
  const [simulationBusy, setSimulationBusy] = useState(false);

  const applyPrivacyResult = (result: RepresentativeResult) => {
    if (!result.ok) throw new Error(result.message);
    if (typeof result.temporary !== 'boolean') throw new Error('无法确认当前对话模式，请重试读取设置。');
    setPrivacy(result.state);
    setLearningPaused(result.learningPaused);
    setTemporary(result.temporary);
    setPrivacyError('');
    return result;
  };

  const readPrivacy = async () => {
    if (!window.launcher?.representative) return false;
    const read = ++privacyRead.current;
    try {
      const result = await window.launcher.representative.getState();
      if (!mounted.current || read !== privacyRead.current) return false;
      applyPrivacyResult(result);
      return true;
    } catch (readError) {
      if (!mounted.current || read !== privacyRead.current) return false;
      setPrivacy(null);
      setPrivacyError(readError instanceof Error ? readError.message : '无法读取隐私设置，请重试。');
      return false;
    }
  };

  const refreshModelStatus = async (responseModel?: string) => {
    try {
      const next = await getAiStatus();
      if (mounted.current) setStatus({ ...next, model: responseModel || next.model });
    } catch {
      if (mounted.current) setStatus((current) => ({ ...current, connection: 'failed', message: '无法读取模型状态，请重试。' }));
    }
  };

  useEffect(() => {
    mounted.current = true;
    void readPrivacy();
    const unsubscribe = window.launcher?.representative.onChanged((result) => {
      if (!mounted.current) return;
      if (result === 'paused') {
        privacyRead.current += 1;
        setLearningPaused(true);
        setLearningNotice('为避免把草稿、角色台词或引用当成本人事实，本次对话已暂停偏好学习。清空本次对话后恢复原模式，已有记忆不变。');
        void readPrivacy();
        return;
      }
      setLearningNotice(result === 'saved' ? '已记住一条明确偏好，可在下方查看、修正或忘记。' : '本次偏好未保存。聊天仍可继续，请检查系统加密服务。');
      void readPrivacy();
    });
    return () => { mounted.current = false; privacyRead.current += 1; unsubscribe?.(); };
  }, [user.id]);

  const discardConversation = () => {
    requestEpoch.current += 1;
    inFlight.current = false;
    setBusy(false);
    setMessages([welcomeMessage]);
    setFailedTurn(null);
    setError('');
    setLearningNotice('');
    setLearningPaused(false);
    setConfirmClear(false);
    setSimulationKey((current) => current + 1);
    setSimulationBusy(false);
    followLatest.current = true;
  };

  const updatePrivacy = async (action: RepresentativeAction) => {
    if (privacyInFlight.current || !window.launcher?.representative) return false;
    privacyInFlight.current = true;
    privacyRead.current += 1;
    setPrivacyBusy(true);
    setPrivacyError('');
    discardConversation();
    setContinuationNotice('');
    setContinuationError('');
    try {
      const result = await window.launcher.representative.update(action);
      if (!mounted.current) return false;
      applyPrivacyResult(result);
      return true;
    } catch (updateError) {
      if (!mounted.current) return false;
      const message = updateError instanceof Error ? updateError.message : '设置未保存，请重试。';
      await readPrivacy();
      if (mounted.current) setPrivacyError((readError) => readError ? `${message} ${readError}` : message);
      return false;
    } finally {
      privacyInFlight.current = false;
      if (mounted.current) setPrivacyBusy(false);
    }
  };

  const updateContinuation = async (action: ContinuationAction) => {
    if (privacyInFlight.current || inFlight.current || temporary || !window.launcher?.representative) return false;
    if (action.kind === 'resume' && input.trim()) return false;
    privacyInFlight.current = true;
    privacyRead.current += 1;
    setPrivacyBusy(true);
    setContinuationError('');
    setContinuationNotice('');
    if (action.kind === 'resume') discardConversation();
    try {
      const response = await window.launcher.representative.continuation(action);
      if (!mounted.current) return false;
      const result = applyPrivacyResult(response);
      if (result.resumed) {
        setWorkspace('chat');
        restoredDraft.current = true;
        setLearningPaused(true);
        setInput(result.resumed.content);
        setContinuationNotice('已放回输入框，尚未发送。本次对话暂停偏好学习；清空本次对话后恢复原模式。');
        inputRef.current?.focus();
      } else setContinuationNotice(action.kind === 'save' ? '已加密保存。下次登录可在这里继续。' : action.kind === 'complete' ? '已完成并删除保存的内容。' : '已移除保存的内容。');
      return true;
    } catch (updateError) {
      if (mounted.current) {
        setContinuationError(updateError instanceof Error ? updateError.message : '待续内容未保存，请重试。');
        // Refresh a stale revision without closing the user's save preview.
        await readPrivacy();
      }
      return false;
    } finally {
      privacyInFlight.current = false;
      if (mounted.current) setPrivacyBusy(false);
    }
  };

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
    if (inFlight.current || privacyInFlight.current || !privacy?.cloudConsent) return;
    inFlight.current = true;
    const epoch = ++requestEpoch.current;
    followLatest.current = true;
    setFailedTurn(null);
    setError('');
    setBusy(true);
    if (turn.savedContent) setLearningPaused(true);
    try {
      const result = await sendAiMessage(turn.message.content, turn.history, temporary, privacy.privacyEpoch, turn.savedContent);
      if (requestEpoch.current !== epoch) return;
      setMessages((current) => [...current, { id: result.responseId || crypto.randomUUID(), role: 'assistant', content: result.text }]);
      setStatus((current) => ({ ...current, configured: true, model: result.model, connection: 'connected' }));
    } catch (submitError) {
      if (requestEpoch.current !== epoch) return;
      setFailedTurn(turn);
      setError(submitError instanceof Error ? submitError.message : 'AI 回复生成失败，请稍后重试。');
      if (window.launcher?.ai) void getAiStatus().then((result) => { if (requestEpoch.current === epoch) setStatus(result); }).catch(() => undefined);
    } finally {
      if (requestEpoch.current === epoch) { inFlight.current = false; setBusy(false); }
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || inFlight.current || privacyInFlight.current || !privacy?.cloudConsent) return;
    const message: ChatMessage = { id: crypto.randomUUID(), role: 'user', content };
    const turn = { message, history: getRecentChatHistory(messages), savedContent: restoredDraft.current };
    setMessages((current) => [...current, message]);
    setConfirmClear(false);
    setInput('');
    restoredDraft.current = false;
    void requestReply(turn);
  };

  const clearConversation = async (nextTemporary = temporary) => {
    if (privacyInFlight.current) return false;
    privacyInFlight.current = true;
    privacyRead.current += 1;
    setPrivacyBusy(true);
    discardConversation();
    setPrivacy(null);
    try {
      if (!window.launcher?.ai) throw new Error('请在桌面软件中操作。');
      await window.launcher.ai.cancel(nextTemporary);
      if (!mounted.current) return false;
      if (!await readPrivacy()) return false;
      setContinuationNotice('');
      setContinuationError('');
      inputRef.current?.focus();
      return true;
    } catch {
      if (mounted.current) { setPrivacy(null); setPrivacyError('无法确认旧请求已取消，请重新读取隐私设置后继续。'); }
      return false;
    } finally {
      privacyInFlight.current = false;
      if (mounted.current) setPrivacyBusy(false);
    }
  };

  const browserPreview = import.meta.env.DEV && !window.launcher?.ai;
  const statusLabel = browserPreview ? '浏览器预览 · 不连接模型' : status.connection === 'connected' ? status.model : status.connection === 'untested' ? '模型配置待验证' : status.connection === 'failed' ? '模型连接失败' : '模型尚未配置';
  const connectionTitle = browserPreview ? '模型在桌面端连接' : status.connection === 'connected' ? '共享模型服务已连接' : status.connection === 'untested' ? '模型配置已载入' : status.connection === 'failed' ? '共享模型服务连接失败' : '需要配置 API';
  const connectionDescription = browserPreview ? '此预览不读取 API 密钥，也不发送模型请求。请在桌面软件中使用 AI 对话。' : status.connection === 'connected' ? 'DeepSeek 已返回真实回复。仅使用当前模式允许的信息。' : status.connection === 'untested' ? '配置已找到，同意云端处理并发送第一条消息后验证连接。' : status.connection === 'failed' ? status.message || '请检查网络、Base URL、模型名称和 API Key。' : '本地模型服务尚未配置，请联系开发人员。';
  const canSend = Boolean(privacy?.cloudConsent && status.configured && status.provider === 'deepseek' && !privacyBusy);
  const latestLearnedMemory = learningNotice.startsWith('已记住') ? privacy?.memories.filter((memory) => memory.sourceKind === 'explicit_message').sort((a, b) => a.updatedAt.localeCompare(b.updatedAt)).at(-1) : undefined;

  return (
    <section className="chat-content" hidden={!active}>
      <header className="chat-page-header"><div><button type="button" onClick={onBack}><Icon name="back"/>返回虚拟分身</button><h1>从今天的想法开始</h1><p>不用填问卷。先交流，再由你决定是否记住偏好。</p></div><span className={`chat-model-status ${status.connection === 'connected' ? 'ready' : ''}`} role="status"><i aria-hidden="true"/>{statusLabel}</span></header>
      <div className="chat-workspaces"><nav aria-label="对话工作区"><button type="button" aria-pressed={workspace === 'chat'} disabled={privacyBusy} onClick={() => { if (workspace !== 'chat') void clearConversation().then((ok) => { if (ok && mounted.current) setWorkspace('chat'); }); }}>日常对话</button><button type="button" aria-pressed={workspace === 'simulation'} disabled={privacyBusy || !privacy} onClick={() => { if (workspace !== 'simulation') void clearConversation().then((ok) => { if (ok && mounted.current) setWorkspace('simulation'); }); }}>私密试答</button></nav><p>切换会清空本次对话和本轮试答；聊天输入框中的文字保留。</p></div>
      <div className="chat-layout">
        {workspace === 'chat' && <article className="chat-window">
          <div className="chat-agent-bar"><span className="chat-agent-avatar">{user.displayName.slice(0, 1).toUpperCase()}</span><div><strong>{user.displayName} 的数字代表</strong><small>{temporary ? '临时对话 · 不使用或新增画像' : !privacy?.cloudConsent ? '当前对话 · 云端处理未授权' : privacy.learningMode === 'learn' ? learningPaused ? '本次对话 · 暂停偏好学习' : '低风险偏好学习中' : privacy.learningMode === 'read_only' ? '只使用已有记忆' : '当前对话 · 不使用画像'}</small></div><div className="chat-clear-actions">{confirmClear ? <><span role="status">清空对话，不删除偏好或待续内容</span><button type="button" onClick={() => setConfirmClear(false)}>取消</button><button type="button" className="confirm-clear" disabled={privacyBusy} onClick={() => { void clearConversation(); }}>确认清空</button></> : <button type="button" disabled={privacyBusy || (messages.length === 1 && !learningPaused)} onClick={() => setConfirmClear(true)}>清空本次对话</button>}</div></div>
          <div ref={messagesRef} className="chat-messages" role="log" aria-live="polite" aria-relevant="additions" aria-busy={busy} onScroll={(event) => {
            const pane = event.currentTarget;
            followLatest.current = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 64;
          }}>
            {!temporary && privacy?.continuations.at(-1) && messages.length === 1 && <div className="representative-notice continuity-return"><p>上次留下：{privacy.continuations.at(-1)!.title}</p><button type="button" disabled={privacyBusy || busy || Boolean(input.trim())} onClick={() => { void updateContinuation({ kind: 'resume', id: privacy.continuations.at(-1)!.id, expectedRevision: privacy.revision }); }}>继续上次的话题或草稿</button><p>只放回输入框，不自动发送；有未保存文字时不会覆盖。</p></div>}
            {messages.map((message) => <div key={message.id} className={`chat-message ${message.role}`}><span>{message.role === 'assistant' ? user.displayName.slice(0, 1).toUpperCase() : '你'}</span><div><small>{message.id === 'welcome' ? '使用提示 · 非模型回复' : message.role === 'assistant' ? '数字代表' : user.displayName}</small><p>{message.content}</p></div></div>)}
            {messages.length === 1 && <div className="chat-suggestions chat-starters"><h2>不知道从哪里开始？</h2><div className="chat-starter-actions">{['帮我把一个想法整理清楚', '帮我起草一段不唐突的表达', '我想聊聊最近的事'].map((suggestion) => <button type="button" key={suggestion} disabled={privacyBusy} onClick={() => { restoredDraft.current = false; setInput(suggestion); inputRef.current?.focus(); }}>{suggestion}</button>)}</div></div>}
            {busy && <div className="chat-message assistant typing" role="status"><span>{user.displayName.slice(0, 1).toUpperCase()}</span><div><small>数字分身</small><p aria-label="正在生成回复"><i/><i/><i/></p></div></div>}
          </div>
          {error && <div className="chat-error" role="alert" aria-live="assertive"><span>{error}</span>{failedTurn && <button type="button" disabled={busy} onClick={() => { void requestReply(failedTurn); }}>重试上一条</button>}</div>}
          <form className="chat-composer" onSubmit={submit}><textarea ref={inputRef} aria-label="发送给数字分身的消息" value={input} disabled={privacyBusy} onChange={(event) => { setInput(event.target.value); if (!event.target.value.trim()) restoredDraft.current = false; }} placeholder={canSend ? '今天有什么想分享的？' : '可以先写下想法，同意右侧云端处理后再发送'} maxLength={2000} onKeyDown={(event) => {
            if (isChatSendShortcut({ key: event.key, ctrlKey: event.ctrlKey, metaKey: event.metaKey, isComposing: event.nativeEvent.isComposing || event.keyCode === 229 })) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}/><div className="chat-composer-actions"><span>{input.length} / 2000 · Ctrl+Enter 发送</span><button type="button" disabled={busy || privacyBusy || !input.trim() || temporary || privacy?.storage !== 'encrypted' || privacy.continuations.length >= 3} onClick={() => setSaveRequest({ id: Date.now(), content: input })}>保存到下次</button><button disabled={busy || !input.trim() || !canSend}>{busy ? '等待回复…' : '发送消息'}</button></div></form>
        </article>}
        {workspace === 'simulation' && (privacy ? <PrivateSimulationPanel key={simulationKey} state={privacy} temporary={temporary} canGenerate={canSend} onBusyChange={setSimulationBusy} onRefresh={async () => { await readPrivacy(); }} onStatusRefresh={refreshModelStatus}/> : <p role="status">暂不能安全读取隐私设置。请先重试读取，再进行私密试答。</p>)}
        <aside className="chat-side-column">
          {privacyError && <div className="chat-error" role="alert"><span>{privacyError}</span><button type="button" disabled={privacyBusy} onClick={() => { setPrivacyError(''); void readPrivacy(); }}>重试读取设置</button></div>}
          {learningNotice && <div className="representative-notice" role="status"><p>{learningNotice}</p>{latestLearnedMemory && <button type="button" disabled={privacyBusy} onClick={() => { void updatePrivacy({ kind: 'forget', id: latestLearnedMemory.id, expectedRevision: privacy!.revision }); }}>不记住这条</button>}</div>}
          <article className="chat-side-card representative-temporary"><label><input type="checkbox" checked={temporary} disabled={privacyBusy || !privacy || browserPreview} onChange={(event) => { void clearConversation(event.target.checked); }}/><span>临时对话</span></label><p>本次对话不使用或新增长期画像。切换时清空当前对话，仍需同意云端处理。整页刷新会结束本次登录，不恢复聊天。</p></article>
          {privacy && <RepresentativePanel state={privacy} busy={privacyBusy} temporary={temporary} paused={learningPaused} canConsent={status.configured && status.provider === 'deepseek'} onChange={updatePrivacy}/>}
          {privacy && <ContinuityPanel state={privacy} draft={input} busy={privacyBusy || busy || simulationBusy} temporary={temporary} error={continuationError} notice={continuationNotice} saveRequest={saveRequest} onAction={updateContinuation}/>}
          {!privacy && !privacyError && <p role="status">{browserPreview ? '浏览器预览不读取账户资料、不保存画像。' : '正在读取隐私设置…'}</p>}
          <details className="chat-side-card chat-config-card chat-connection-details" open={status.connection === 'failed'}><summary>模型连接详情<span>{connectionTitle}</span></summary><p>{connectionDescription}</p></details>
        </aside>
      </div>
    </section>
  );
}
