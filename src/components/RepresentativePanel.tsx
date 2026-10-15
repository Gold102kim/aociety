import { useState } from 'react';
import { memoryChoices, type RepresentativeAction, type RepresentativeState } from '../../electron/representative-types';

export function RepresentativePanel({ state, busy, canConsent, temporary, paused, onChange }: {
  state: RepresentativeState;
  busy: boolean;
  canConsent: boolean;
  temporary: boolean;
  paused: boolean;
  onChange: (action: RepresentativeAction) => Promise<boolean>;
}) {
  const [confirmReset, setConfirmReset] = useState(false);
  const modeLabel = temporary ? '临时对话中暂停使用画像' : !state.cloudConsent ? '云端处理未授权' : state.learningMode === 'learn' ? paused ? '本次对话已暂停偏好学习' : '偏好学习中' : state.learningMode === 'read_only' ? '只使用已有记忆' : '不使用画像';
  return <article className="chat-side-card representative-panel" aria-busy={busy}>
    <div className="representative-heading"><h2>记忆与隐私</h2><p className="representative-mode" role="status">{modeLabel} · {temporary ? '长期记忆已隐藏' : `${state.memories.length} 条记忆`}</p></div>
    {busy && <p role="status">正在保存设置…</p>}
    <label className="representative-consent"><input type="checkbox" checked={state.cloudConsent} disabled={busy || (!canConsent && !state.cloudConsent)} onChange={(event) => { void onChange({ kind: 'consent', enabled: event.target.checked, expectedRevision: state.revision }); }}/><span>同意 DeepSeek 云端处理<small>发送昵称、消息及必要上下文至 DeepSeek；试答发送测试情境。旧问卷不发送。撤回不会撤回已发出的数据。</small></span></label>
    {state.storage === 'session' && <p role="status">系统加密不可用：授权仅在本次登录有效，长期画像已停用。</p>}
    <label className="representative-field">如何使用我的画像<select value={state.learningMode} disabled={busy || state.storage !== 'encrypted'} onChange={(event) => { void onChange({ kind: 'mode', mode: event.target.value as RepresentativeState['learningMode'], expectedRevision: state.revision }); }}>
      <option value="off">不读取、不学习</option><option value="read_only">停止学习，仅使用已有记忆</option><option value="learn">允许学习明确的低风险偏好</option>
    </select></label>
    <p className="representative-learning-hint">学习默认关闭，不推断人格。</p>
    {paused && state.learningMode === 'learn' && !temporary && <p>当前语境不用于学习。清空本次对话后恢复原模式；已有记忆不会删除。</p>}
    <p className="representative-change-notice">修改授权、模式或记忆会清空本次对话和本轮试答，避免继续使用旧上下文。聊天输入框中的草稿保留。</p>
    {temporary ? <p>临时对话不展示长期记忆和来源。原有记忆没有删除，关闭临时对话后可继续管理。</p> : <details className="representative-memories"><summary>查看与管理记忆（{state.memories.length}）</summary>
      {!state.memories.length && <p>还没有保存偏好。不开启学习也能聊天。</p>}
      {state.memories.map((memory) => <div className="representative-memory" key={memory.id}>
        <strong>{memory.key === 'replyStyle' ? '回答方式' : '音乐偏好'}</strong>
        <label className="representative-field">{memory.sourceKind === 'user_correction' ? '本人已修正' : '明确自述'}<select value={memory.value} disabled={busy} onChange={(event) => { void onChange({ kind: 'correct', id: memory.id, value: event.target.value, expectedRevision: state.revision }); }}>{memoryChoices[memory.key].map((choice) => <option key={choice}>{choice}</option>)}</select></label>
        <p>来源：{memory.source}</p><time dateTime={memory.updatedAt}>{new Date(memory.updatedAt).toLocaleString('zh-CN')}</time>
        <button type="button" disabled={busy} onClick={() => { void onChange({ kind: 'forget', id: memory.id, expectedRevision: state.revision }); }}>忘记这条偏好</button>
      </div>)}
    </details>}
    <details className="representative-policy-details"><summary>学习范围与保存方式</summary><p>开启学习后，首版仅识别回答长短和五种音乐类型的明确表达，不推断人格。</p><p>试答发送昵称与测试情境。对话和试答只使用各自模式允许的偏好。</p><p className="representative-history">完整聊天记录不落盘，仅在当前窗口临时保留。清空或退出账户后移除；偏好记忆和主动保存的待续内容需单独删除。</p></details>
    {confirmReset ? <div className="representative-reset"><p>删除全部偏好和待续内容，并关闭学习和云端授权？旧问卷不会被删除。</p><button type="button" disabled={busy} onClick={() => { setConfirmReset(false); }}>取消</button><button type="button" disabled={busy} onClick={() => { void onChange({ kind: 'reset', expectedRevision: state.revision }).then((ok) => { if (ok) setConfirmReset(false); }); }}>确认重置</button></div>
      : <button type="button" className="representative-reset-trigger" disabled={busy} onClick={() => setConfirmReset(true)}>重置对话画像与授权</button>}
  </article>;
}
