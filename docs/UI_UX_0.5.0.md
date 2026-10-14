# Aociety UI / UX 0.5.0

## Scope

Home, primary navigation, avatar appearance, chat, and shared visual foundations.
DeepSeek configuration, account storage, UE game configuration, and companion rendering are unchanged.

## Design decisions

- Quiet navy surfaces, mint default accent, readable Chinese text, 12px cards, consistent 42px actions.
- Existing user-selected accent colors remain supported.
- Home prioritizes one real action: enter the local forest-town game. Three working shortcuts replace nonfunctional news cards and simulated activity.
- Forest illustration is an original lightweight SVG, explicitly labeled a concept illustration, not a gameplay screenshot.
- Chat keeps the composer in the window; only messages and the information column scroll independently.
- Clearing a conversation requires a second confirmation; suggestion clicks focus the composer. Existing failed-message retry and draft retention stay intact.
- Avatar appearance shows the 3D preview alongside personality information and a direct chat action.
- Keyboard focus rings, reduced-motion behavior, and dismissible feedback remain available.

## Design artifacts

- Canva direction board and editable Figma references are kept in the project owner's connected accounts; private editing links are not published in the source repository.
- Figma scope: dark foundations, button/navigation/shortcut components, Home and Chat reference compositions. This is a scoped UI family, not a complete product design system.
- Figma font: Noto Sans SC. The desktop app uses the same family when installed, otherwise Microsoft YaHei UI / Segoe UI; exact text metrics may differ.
- Source tokens are authoritative. Community Simple Design System was inspected; custom local components match the existing product rather than introducing its unrelated Inter typography.
- Canva is an AI-generated direction board only. Its sample task/reward copy is not a shipped feature; implementation copy is verified against existing functionality.

## Validation

`pnpm check` includes type checks, secrets, account, AI, contracts, game integration, assets, performance, and production-output checks.
Visual checks target 1120 × 720 and 1440 × 900, including composer visibility, navigation, retry, clear confirmation, and alternate accent colors.
Browser preview has no desktop AI bridge; its disconnected status and failed requests are expected and do not indicate a change to the actual DeepSeek configuration.
Passed: full check, all nine accent colors at 4.5:1 or higher for action text, no horizontal overflow at 1440×900, chat composer bottom below 700px at 1120×720 even with a failed turn, retry retains a new draft with one user message, cancelled clear does not delete the conversation, and navigation retains messages/drafts.
Passed: corrected 265px avatar information column and visible launch action at minimum window size; loaded SVG; working world-detail navigation and dismissible browser-launch feedback.
Production build: 10 assets, initial JavaScript approximately 207.1 KiB, retaining all lazy page/3D chunks.
Passed: 1440×900 chat composer ends at approximately 875px with no horizontal overflow; deep-sea blue theme uses contrast-tested dark action text.
Passed: packaged 0.5.0 launcher in the E-drive delivery directory starts UE and reaches its main menu.
Delivery: E:\aociety\EchoVerse启动器.exe. Previous source/build/executable backup: E:\aociety\备份\UI改版前-0.4.2-20261014-123831.
Portable SHA-256: 613BDD268F7BA2F68A381887B04E118C3CE0334EE15FD09B7FDCC598E334BA85.

## Figma implementation ledger

File identifier is retained in local design-generation records, which are excluded from source publication. Page: 0:1 (initially empty).
Ownership: all new local Aociety 0.5 components and frames in this newly created file.
Acceptance: semantic color/spacing/radius variables, Noto Sans SC text, reusable text-property components, editable Home/Chat compositions, no full-screen raster UI layers.
Completed: foundations, variants, both screen compositions, screenshot inspection and targeted height/alignment repairs.
Collections: 3:2 and 3:14; 30 variables. Nine local components, two variant sets, twenty screen instances.
Home frame: 4:4 (121 descendants). Chat frame: 4:126 (75 descendants before the alignment wrapper).
Button variants: 4:2. Navigation variants: 4:3. Shortcut component: 3:52. Notes: 4:202.
Validation: 101 text layers all use Noto Sans SC; zero raster image fills. The forest scene consists of native vector layers.
Last repair: welcome/copy heights 4:40 and 4:41; right-aligned user-turn wrapper 5:42 and bubble 4:176.
Source scripts are one-shot, file-specific generation records; do not rerun into the populated file.
