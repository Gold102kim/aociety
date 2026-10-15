import { useEffect, useRef, useState } from 'react';
import type { RepresentativeState } from '../../electron/representative-types';
import { evaluationDimensions, simulationLabels, simulationModes, type EvaluationDimension, type EvaluationRating, type SimulationMode, type SimulationReply } from '../../electron/simulation-types';

type Trial = { reply: SimulationReply; ratings: Partial<Record<EvaluationDimension, EvaluationRating>> };

export function PrivateSimulationPanel({ state, temporary, canGenerate, onBusyChange, onRefresh, onStatusRefresh }: {
  state: RepresentativeState;
  temporary: boolean;
  canGenerate: boolean;
  onBusyChange: (busy: boolean) => void;
  onRefresh: () => Promise<void>;
  onStatusRefresh: (responseModel?: string) => Promise<void>;
}) {
  const [scenario, setScenario] = useState('');
  const [reference, setReference] = useState('');
  const [mode, setMode] = useState<SimulationMode>('generic');
  const [trials, setTrials] = useState<Partial<Record<SimulationMode, Trial>>>({});
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [setupOpen, setSetupOpen] = useState(true);
  const epoch = useRef(0);
  const inFlight = useRef(false);
  const stopping = useRef(false);
  const mounted = useRef(true);
  const firstField = useRef<HTMLTextAreaElement>(null);
  const resultHeadings = useRef<Partial<Record<SimulationMode, HTMLHeadingElement | null>>>({});
  const lastRevision = useRef(state.revision);
  const profileAllowed = !temporary && state.storage === 'encrypted' && state.learningMode !== 'off';
  const entries = simulationModes.flatMap((key) => trials[key] ? [trials[key]!] : []);
  const locked = entries.length > 0 || busy || blocked;
  const rated = entries.reduce((total, trial) => total + Object.values(trial.ratings).filter(Boolean).length, 0);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; epoch.current += 1; onBusyChange(false); };
  }, [onBusyChange]);

  useEffect(() => {
    if (lastRevision.current === state.revision) return;
    lastRevision.current = state.revision;
    epoch.current += 1;
    // A changed profile cannot be compared with the previous round's output.
    inFlight.current = false;
    setBusy(false);
    onBusyChange(false);
    setTrials({});
    setSetupOpen(true);
    setNotice('资料版本已改变，已清除旧试答与评分；情境和对照答案仍在输入框。');
  }, [state.revision, onBusyChange]);

  const generate = async () => {
    if (inFlight.current || blocked || !canGenerate || !scenario.trim()) return;
    inFlight.current = true;
    const request = ++epoch.current;
    setBusy(true);
    onBusyChange(true);
    setError('');
    setNotice('');
    setTrials((current) => { const next = { ...current }; delete next[mode]; return next; });
    try {
      if (!window.launcher?.ai) throw new Error('请在桌面软件中生成试答。');
      // The optional reference answer and ratings are deliberately not sent.
      const result = await window.launcher.ai.simulate({ scenario: scenario.trim(), mode, temporary, privacyEpoch: state.privacyEpoch, expectedRevision: state.revision });
      if (!mounted.current || request !== epoch.current) return;
      if (!result.ok) throw new Error(result.message);
      setTrials((current) => ({ ...current, [mode]: { reply: result.reply, ratings: {} } }));
      setSetupOpen(false);
      void onStatusRefresh(result.reply.model);
      requestAnimationFrame(() => {
        resultHeadings.current[mode]?.scrollIntoView({ block: 'start' });
        resultHeadings.current[mode]?.focus({ preventScroll: true });
      });
    } catch (failure) {
      if (mounted.current && request === epoch.current) {
        setError(failure instanceof Error ? failure.message : '试答生成失败，请重试。');
        void onStatusRefresh();
      }
    } finally {
      if (mounted.current && request === epoch.current) { inFlight.current = false; setBusy(false); onBusyChange(false); }
    }
  };

  const stop = async () => {
    if (!window.launcher?.ai || stopping.current) return;
    stopping.current = true;
    epoch.current += 1;
    setBusy(true);
    onBusyChange(true);
    try {
      await window.launcher.ai.cancel();
      if (!mounted.current) return;
      inFlight.current = false;
      setBlocked(false);
      setError('');
      setNotice('已停止本次生成，晚到结果不会显示。输入和其他配置的试答保留。');
    } catch {
      if (mounted.current) { setBlocked(true); setError('无法确认请求已停止，已暂停生成。请重试停止或切换回日常对话。'); }
    } finally {
      stopping.current = false;
      if (mounted.current) { setBusy(false); onBusyChange(false); }
    }
  };

  const reset = () => {
    if (busy || blocked) return;
    epoch.current += 1;
    setTrials({}); setScenario(''); setReference(''); setError(''); setNotice(''); setSetupOpen(true);
    requestAnimationFrame(() => firstField.current?.focus());
  };

  return <article className="chat-window simulation-panel" aria-busy={busy}>
    <header className="simulation-header"><h2>试试像不像我</h2><p>仅供本人预览，不是本人发言，不会自动代发或执行操作。</p></header>
    <div className="simulation-scroll">
      <form className="simulation-form" onSubmit={(event) => { event.preventDefault(); void generate(); }}>
        <details className="simulation-setup" open={setupOpen} onToggle={(event) => setSetupOpen(event.currentTarget.open)}><summary>{entries.length ? `本轮情境：${scenario.slice(0, 45)}${scenario.length > 45 ? '…' : ''}` : '填写一个情境，不需要补充问卷'}</summary>
        <label>测试情境<textarea ref={firstField} value={scenario} onChange={(event) => setScenario(event.target.value)} maxLength={2000} required readOnly={locked} placeholder="例如：朋友临时邀约，但我已经安排了独处时间。可以怎么回应？"/></label>
        <p>请用虚构或已获授权、去除身份信息的情境。</p>
        <details><summary>先写下我会怎样回应（可选）</summary><label>我的对照答案<textarea value={reference} onChange={(event) => setReference(event.target.value)} maxLength={2000} readOnly={locked}/></label><p>只在当前窗口对照，不上传给模型，不作为画像证据。先写再生成，更容易发现差别。</p></details>
        </details>
        <label>本次试答配置<select value={mode} disabled={busy || blocked} onChange={(event) => setMode(event.target.value as SimulationMode)}>{simulationModes.map((key) => <option key={key} value={key} disabled={key !== 'generic' && !profileAllowed}>{simulationLabels[key]}</option>)}</select></label>
        <p>{mode === 'generic' ? '不使用任何画像偏好，只提供昵称和测试情境。' : mode === 'confirmed' ? '仅使用记忆面板中本人明确修正过的偏好，不读取旧问卷。' : '使用已确认修正和对话中明确学到的偏好，不读取旧问卷、待续草稿或聊天历史。'}</p>
        {!profileAllowed && <p>临时对话、关闭画像或系统加密不可用时，只能选择通用回复。</p>}
        <p>每次生成向 DeepSeek 上传情境、昵称和允许的偏好，发起 1 次请求，费用由当前配置账户承担。对照答案、评分不上传。</p>
        {!canGenerate && <p role="status">请先在“记忆与隐私”同意云端处理，并确认桌面端配置了 DeepSeek。</p>}
        {locked && <p>情境和对照答案已锁定。重新生成会清除该配置的旧试答与评分；换题请清空本轮。</p>}
        <div className="simulation-actions"><button type="submit" disabled={busy || blocked || !canGenerate || !scenario.trim()}>{busy ? '正在生成试答…' : trials[mode] ? '重新生成当前配置（1次请求）' : '生成当前配置（1次请求）'}</button>{(busy || blocked) && <button type="button" onClick={() => { void stop(); }}>{blocked ? '重试停止' : '停止生成'}</button>}<button type="button" disabled={busy || blocked || (!scenario && !reference && !entries.length)} onClick={reset}>清空本轮</button></div>
        <details><summary>数据范围与当前证据</summary><p>证据仍有限：{state.memories.filter((memory) => memory.sourceKind === 'user_correction').length} 条本人修正、{state.memories.filter((memory) => memory.sourceKind === 'explicit_message').length} 条对话偏好。不能据此认定人格相似。</p><p>不读取旧问卷、待续草稿或聊天历史。清空本轮、切换工作区、修改隐私或退出账户会移除本轮内容；评分不改变偏好。</p></details>
      </form>
      {error && <div className="simulation-error" role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={() => { void onRefresh(); }}>读取最新设置</button></div>}
      {notice && <p role="status">{notice}</p>}
      <section className="simulation-results" aria-label="本轮试答与分项评测" aria-live="polite" aria-relevant="additions">
        {!entries.length && !busy && <p>生成后可在这里逐项比较；没有评分或未生成的配置不会显示成评测成功。</p>}
        {reference && entries.length > 0 && <details><summary>查看我的对照答案（未上传）</summary><p className="simulation-text">{reference}</p></details>}
        {entries.map(({ reply, ratings }) => <section className="simulation-result" key={reply.mode} aria-label={`${simulationLabels[reply.mode]}试答`}>
          <h3 tabIndex={-1} ref={(node) => { resultHeadings.current[reply.mode] = node; }}>{simulationLabels[reply.mode]}</h3><p className="simulation-meta">{reply.model} · 资料版本 {reply.profileRevision} · {(reply.durationMs / 1000).toFixed(1)} 秒 · 使用 {reply.usedMemoryKeys.length} 条偏好</p>
          <time className="simulation-meta" dateTime={reply.createdAt}>{new Date(reply.createdAt).toLocaleString('zh-CN')}</time>
          <p className="simulation-meta">提示版本：{reply.promptVersion}</p>
          <p className="simulation-text">{reply.text}</p>
          <fieldset><legend>我来判断，不自动打分</legend><div className="simulation-ratings">{evaluationDimensions.map(({ key, label }) => <label key={key}>{label}<select aria-label={`${simulationLabels[reply.mode]} · ${label}`} value={ratings[key] ?? ''} disabled={busy || blocked} onChange={(event) => {
            const value = event.target.value as EvaluationRating;
            setTrials((current) => ({ ...current, [reply.mode]: { reply, ratings: { ...current[reply.mode]?.ratings, [key]: value } } }));
          }}><option value="">未评分</option><option value="yes">符合</option><option value="partly">部分符合</option><option value="no">不符合</option><option value="unknown">无法判断</option></select></label>)}</div></fieldset>
        </section>)}
        {entries.length > 0 && <p>本轮已记录 {rated} 项本人评价，不合并成“人格复刻百分比”。{new Set(entries.map((trial) => trial.reply.model)).size > 1 ? '模型版本不同，不宜直接比较配置效果。' : '这是当前场景的主观反馈，不是心理测量或普遍相似度。'}</p>}
      </section>
      <p className="simulation-retention">本轮情境、答案、试答和评分不落盘；清空本轮、切换工作区、修改隐私或退出账户后移除。旧问卷与已保存的偏好不受本轮评分影响。</p>
    </div>
  </article>;
}
