# Python service review

The launcher and forest residents continue to use the project-local DeepSeek route. This review does not change model credentials, call paid models, or migrate user accounts.

## Runtime improvements

- DeepSeek SDK automatic retries are disabled. Its I/O timeout is no longer longer than the caller's configured deadline.
- Dialogue and background execution have separate bounded slots. A timed-out or cancelled request keeps its slot until the underlying operation actually ends. New requests fail fast instead of accumulating a thread-pool queue.
- Cooldown uses a monotonic clock. A concurrent successful request cannot clear a newer failure's cooldown.
- Resident and hardware application shutdown close model transports and executors. Shutdown rejects new work and does not wait indefinitely for remote I/O.
- Hardware emotion and world WebSocket processing runs in a small bounded worker pool, keeping blocking analysis off the event loop. Emotion WebSockets now return the actual fused analysis result instead of discarding the cloud result.
- The optional hardware pipeline's TTS voice label no longer references a nonexistent class attribute.
- Local-model launch commands default to `127.0.0.1` and do not enable reload in normal operation. Use `python scripts/start_all.py --host 0.0.0.0` only when LAN access is intentionally required; `--reload` is an explicit development option. Exposing the unauthenticated hardware endpoints on a network requires separate access control.

Python cannot forcibly terminate an already running thread. A caller timeout or WebSocket cancellation is **not** a guarantee that an upstream HTTP request has stopped or that no charge can occur. Bounded admission, disabled SDK retries, I/O timeouts and transport closure limit the damage; they do not provide remote cancellation.

## Optional legacy OpenClaw assistant privacy

The legacy hardware assistant is not the current forest resident route. It previously copied the desktop's `.codex/auth.json` and `cap_sid` into its own runtime without a separate decision, and deleted the old runtime directory on each preparation.

That implicit sharing and recursive deletion have been removed. The helper ignores the inherited global `CODEX_HOME`, uses its application-configured `codex_home`, and defaults to `isolated-runtime`. Existing account files in the old `runtime` are preserved but not silently reused.

Only an explicit `OPENCLAW_ALLOW_SHARED_CODEX_AUTH=1` enables copying from a chosen `OPENCLAW_SHARED_CODEX_HOME` (or the desktop `.codex` directory when no source is specified). Shared credentials go into a separate `shared-runtime`; switching sharing off does not reuse that directory. Do not enable this when distributing the project, and never upload either runtime's credentials or account data.

OpenClaw state discovery is also confined to the explicitly configured application state directory or the application's own workspace `.openclaw`. It no longer scans the user's global `.openclaw`, Antigravity accounts, APPDATA, or a workspace parent. Cross-application state sharing needs **both** `OPENCLAW_ALLOW_SHARED_STATE=1` and an explicitly selected `OPENCLAW_SHARED_STATE_DIR`. A sharing flag alone does not authorize a broad account-directory search. Existing directories are preserved; specifying an existing `OPENCLAW_STATE_DIR` continues to use that deliberate configuration.

An old assistant that relied on an automatically inherited desktop login may now require an application-specific provider/login configuration. Opt-in is available when the user intentionally wants shared authentication, but is not needed for DeepSeek forest dialogue. Device-signing through the optional OpenClaw WebSocket bridge requires `cryptography`; it is loaded only when that bridge is used, not during resident startup or the standard offline test suite.

## Offline verification

Install `requirements-resident.txt`, then run:

```powershell
python -B -m unittest discover -s tests -v
```

The suite uses the Python standard library's `unittest`; neither pytest nor python-dotenv is required. Tests disable `.env` loading, mock model/TTS clients, use only temporary account fixtures, and never contact real model endpoints or read desktop credentials. Async tests need ordinary local socket permissions on Windows because asyncio creates an internal loopback socket pair.

## Audit boundaries

All reviewed Python modules passed syntax parsing. The large legacy market-world engine contains overwritten duplicate method definitions; removing them without its original gameplay regression coverage is deferred. Hardware vision/ASR paths still load heavyweight models per request and use experimental adapters; those paths are not exercised by the current forest demo, and this change does not claim measured hardware inference improvements.
