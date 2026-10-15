import { useEffect, useRef, useState } from 'react';
import { continuationLimit, type ContinuationAction, type RepresentativeState, type SavedContinuation } from '../../electron/representative-types';

export function ContinuityPanel({ state, draft, busy, temporary, error, notice, saveRequest, onAction }: {
  state: RepresentativeState;
  draft: string;
  busy: boolean;
  temporary: boolean;
  error: string;
  notice: string;
  saveRequest: { id: number; content: string } | null;
  onAction: (action: ContinuationAction) => Promise<boolean>;
}) {
  const [preview, setPreview] = useState<Pick<SavedContinuation, 'kind' | 'title' | 'content'> | null>(null);
  const [confirm, setConfirm] = useState<{ id: string; kind: 'complete' | 'remove' } | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!saveRequest) return;
    setPreview({ kind: 'draft', title: saveRequest.content.trim().split('\n')[0].slice(0, 60), content: saveRequest.content });
    requestAnimationFrame(() => {
      titleRef.current?.closest('form')?.scrollIntoView({ block: 'start' });
      titleRef.current?.focus({ preventScroll: true });
    });
  }, [saveRequest]);
  const unavailable = temporary || state.storage !== 'encrypted';
  const items = [...state.continuations].reverse();
  const row = (item: SavedContinuation) => <div className="continuity-item" key={item.id}>
    <strong>{item.title}</strong>
    <p>{item.kind === 'topic' ? '待聊话题' : '文字草稿'} · <time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleDateString('zh-CN')}</time></p>
    <details><summary>查看已保存内容</summary><p className="continuity-content">{item.content}</p></details>
    <div className="continuity-actions">
      <button type="button" disabled={busy || Boolean(draft.trim())} onClick={() => { void onAction({ kind: 'resume', id: item.id, expectedRevision: state.revision }); }}>放回输入框</button>
      <button type="button" disabled={busy} onClick={() => setConfirm({ id: item.id, kind: 'complete' })}>标记完成</button>
      <button type="button" disabled={busy} onClick={() => setConfirm({ id: item.id, kind: 'remove' })}>移除</button>
    </div>
    {confirm?.id === item.id && <div className="continuity-confirm"><p>{confirm.kind === 'complete' ? '完成后' : '移除后'}删除这份已保存内容，不保留归档；不撤回已发送的消息。</p><div className="continuity-actions"><button type="button" disabled={busy} onClick={() => setConfirm(null)}>取消</button><button type="button" disabled={busy} onClick={() => { void onAction({ ...confirm, expectedRevision: state.revision }).then((ok) => { if (ok) setConfirm(null); }); }}>{confirm.kind === 'complete' ? '完成并移除' : '确认移除'}</button></div></div>}
  </div>;

  return <article className="chat-side-card continuity-panel" aria-busy={busy}>
    <h2>下次继续</h2>
    <p>只保存你确认的片段，不保存整段聊天，不自动发给模型。</p>
    {error && <p role="alert" className="continuity-error">{error}</p>}
    {notice && <p role="status" className="continuity-notice">{notice}</p>}
    {unavailable ? <p>{temporary ? '临时对话中不显示、保存或恢复待续内容。' : '系统加密不可用，暂不能保存或恢复内容。'}</p> : <>
      {items[0] ? row(items[0]) : <p>还没有待续内容。可以留一个想聊的话题，或保存输入框中的草稿。</p>}
      {items.length > 1 && <details className="continuity-more"><summary>其他待续内容（{items.length - 1}）</summary>{items.slice(1).map(row)}</details>}
      {Boolean(draft.trim()) && items.length > 0 && <p>输入框已有文字。先保存或清空，再恢复，避免覆盖。</p>}
      {!preview ? <button type="button" disabled={busy || items.length >= continuationLimit} onClick={() => {
        setPreview({ kind: draft.trim() ? 'draft' : 'topic', title: draft.trim().split('\n')[0].slice(0, 60), content: draft });
        requestAnimationFrame(() => titleRef.current?.focus());
      }}>{draft.trim() ? '预览并保存当前草稿' : '留一个待聊话题'}</button> : <form className="continuity-preview" onSubmit={(event) => {
        event.preventDefault();
        void onAction({ kind: 'save', item: preview, expectedRevision: state.revision }).then((ok) => { if (ok) setPreview(null); });
      }}>
        <h3>确认要保存的内容</h3>
        <label>类型<select value={preview.kind} disabled={busy} onChange={(event) => setPreview({ ...preview, kind: event.target.value as SavedContinuation['kind'] })}><option value="topic">待聊话题</option><option value="draft">文字草稿</option></select></label>
        <label>标题<input ref={titleRef} value={preview.title} maxLength={60} required disabled={busy} onChange={(event) => setPreview({ ...preview, title: event.target.value })}/></label>
        <label>保存内容<textarea value={preview.content} maxLength={2000} required disabled={busy} onChange={(event) => setPreview({ ...preview, content: event.target.value })}/></label>
        <p>这份内容将加密保存在本机，不会作为个人偏好。请勿保存密码、密钥或他人的敏感资料。</p>
        <div className="continuity-actions"><button type="button" disabled={busy} onClick={() => setPreview(null)}>取消保存</button><button disabled={busy || !preview.title.trim() || !preview.content.trim() || items.length >= continuationLimit}>确认加密保存</button></div>
      </form>}
      <p className="continuity-limit">{items.length} / {continuationLimit} 条待续内容 · 仅本机，不跨设备同步</p>
    </>}
  </article>;
}
