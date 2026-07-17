import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

type LogLevel = 'info' | 'warn' | 'error';

const MAX_LOG_BYTES = 2 * 1024 * 1024;
let logFilePath: string | null = null;

function redactString(value: string) {
  const home = os.homedir();
  return value
    .replaceAll(home, '[USER_HOME]')
    .replace(/\bsk-[A-Za-z0-9_-]{16,}\b/g, '[REDACTED_KEY]')
    .slice(0, 10_000);
}

function sanitize(value: unknown, depth = 0): unknown {
  if (typeof value === 'string') return redactString(value);
  if (typeof value === 'number' || typeof value === 'boolean' || value === null) return value;
  if (depth >= 3) return '[TRUNCATED]';
  if (Array.isArray(value)) return value.slice(0, 20).map((entry) => sanitize(entry, depth + 1));
  if (typeof value === 'object' && value) {
    return Object.fromEntries(Object.entries(value).slice(0, 30).map(([key, entry]) => [key, sanitize(entry, depth + 1)]));
  }
  return String(value);
}

export function initializeLogger(userDataDirectory: string) {
  try {
    const directory = path.join(userDataDirectory, 'logs');
    fs.mkdirSync(directory, { recursive: true });
    logFilePath = path.join(directory, 'main.log');
    if (fs.existsSync(logFilePath) && fs.statSync(logFilePath).size >= MAX_LOG_BYTES) {
      const previousPath = path.join(directory, 'main.previous.log');
      fs.rmSync(previousPath, { force: true });
      fs.renameSync(logFilePath, previousPath);
    }
  } catch {
    logFilePath = null;
  }
}

export function logEvent(level: LogLevel, event: string, details: Record<string, unknown> = {}) {
  if (!logFilePath) return;
  try {
    const record = {
      timestamp: new Date().toISOString(),
      level,
      event,
      details: sanitize(details),
    };
    fs.appendFileSync(logFilePath, `${JSON.stringify(record)}\n`, { encoding: 'utf8', mode: 0o600 });
  } catch {
    // Diagnostics must never prevent the launcher from starting or closing.
  }
}

export function logError(event: string, error: unknown, details: Record<string, unknown> = {}) {
  const normalized = error instanceof Error
    ? { name: error.name, message: error.message, stack: error.stack || '' }
    : { value: error };
  logEvent('error', event, { ...details, error: normalized });
}
