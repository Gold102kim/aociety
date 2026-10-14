# Aociety 0.5.1 — Glass appearance

This is a Windows/Electron CSS interpretation of the iOS glass aesthetic, not an iOS/SwiftUI port or an implementation of Apple's native Liquid Glass shader.
Reference: [Apple materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials).

## Appearance

- Static navy, cyan and violet background light; no moving wallpaper, refraction shader, pointer-following script or continuously animated blur.
- Floating frosted sidebar, translucent shortcut cards, soft edge highlights and rounded controls.
- Chat and avatar preview use approximately 90% opaque panels with no backdrop filter. Nested old blur is disabled.
- Existing favorite-color accents, navigation, message retention, retries, accounts, DeepSeek and UE integration remain intact.

## Clarity

The titlebar's **玻璃 / 清晰** control toggles reduced transparency. Clear mode removes backdrop blur and background light while retaining the same layout and foreground colors.
The only preference storage key is `echoverse:appearance:reduce-transparency`; denied local storage does not prevent startup or switching appearance.
CSS also contains fallbacks for `prefers-reduced-transparency`, `prefers-contrast`, `forced-colors` and unsupported backdrop-filter. App watches system preference changes and labels the effective mode as 清晰 · 系统 when forced by accessibility. These media fallbacks are checked structurally; system accessibility settings are not changed by the app.

## Verification

- UI foundations: all nine action accent colors meet the existing 4.5:1 contrast check; storage defaults, saved states and failure cases are covered.
- Manual preview: 1120×720 and 1440×900; glass/clear toggle and persisted state after reload; no horizontal overflow; chat composer remains visible; draft retained across page navigation.
- Shader/GPU scope: no filter on Canvas ancestors, no animated glass effect, no new timers or dependencies. The existing 30 FPS scheduler still applies.
- No native GPU performance improvement is claimed; visual checks and render-budget regression tests do not constitute hardware benchmarking.

Full `pnpm check` passed. Production: 10 assets, initial JavaScript approximately 208.5 KiB (under the unchanged 225 KiB budget).
Screenshots: `artifacts/home-glass-0.5.1.png`, `chat-glass-0.5.1.png`, `chat-clear-0.5.1.png`.
Manual measurements at 1120×720: chat composer bottom approximately 699px, avatar launch footer approximately 709px; no Canvas ancestor has filter/backdrop-filter. Clear-mode titlebar/profile/messages/composer/suggestions use opaque RGB backgrounds.
Final portable SHA-256: 03F95DBFF1382C3D66A08D9F4D650A53E6FE3517D6EA242BB1D554DECD237E7B.
Delivery: `E:\aociety\EchoVerse启动器.exe`. Deployment backs up the prior source/build/executable and verifies protected files' hashes without exposing their contents.
0.5.1 packaged launcher reached the UE main menu. A final CSS-only account/profile input correction was then visually verified and repackaged; production output and UI foundations were rechecked.
Login verification at 1120×720: input radius 15px, lighter placeholder text, action bottom approximately 542px, no horizontal overflow. Proof: `artifacts/login-glass-0.5.1.png`.
Original 0.5.0 backup: `E:\aociety\备份\玻璃改版前-0.5.0-20261014-195904`.
