import type { ChildProcess } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

export async function waitForServiceHealth(child: ChildProcess, healthUrl: string, timeoutMs: number) {
  const lifetime = new AbortController();
  let failure: Error | null = null;
  const fail = (error: Error) => { failure = error; lifetime.abort(); };
  const onExit = (code: number | null) => fail(new Error(`服务进程已退出（代码 ${code ?? '未知'}）。`));
  const onError = (error: Error) => fail(error);
  child.once('exit', onExit);
  child.once('error', onError);
  const timeout = setTimeout(() => lifetime.abort(), timeoutMs);
  try {
    if (child.exitCode !== null || child.signalCode !== null) onExit(child.exitCode);
    while (!lifetime.signal.aborted) {
      try {
        const response = await fetch(healthUrl, {
          signal: AbortSignal.any([lifetime.signal, AbortSignal.timeout(1500)]),
          cache: 'no-store',
        });
        await response.body?.cancel();
        if (response.ok && !lifetime.signal.aborted) return true;
      } catch {
        // Retry a transient health failure only while the child is alive.
      }
      if (!lifetime.signal.aborted) {
        try { await delay(250, undefined, { signal: lifetime.signal }); } catch { /* Stopped. */ }
      }
    }
    if (failure) throw failure;
    return false;
  } finally {
    clearTimeout(timeout);
    child.removeListener('exit', onExit);
    child.removeListener('error', onError);
  }
}
