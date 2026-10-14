import { lazy, useCallback, useEffect, useRef, useState } from 'react';
import { LauncherUser, signOut } from './auth';
import { TitleBar } from './components/LauncherUi';
import { getDevelopmentPreviewUser } from './dev/previewUser';
import { AuthScreen, QuestionnaireScreen } from './pages/AccountFlow';
import { BootSequence } from './pages/BootSequence';
import { PageLoadBoundary } from './components/PageLoadBoundary';
import { getThemeStyle } from './theme';
import { readReducedTransparency, reducedTransparencyMediaQuery, saveReducedTransparency } from './appearance';

const CompanionApp = lazy(() => import('./pages/CompanionApp').then((module) => ({ default: module.CompanionApp })));
const LauncherHome = lazy(() => import('./pages/LauncherHome').then((module) => ({ default: module.LauncherHome })));

function LauncherApplication() {
  const [reducedTransparency, setReducedTransparency] = useState(() => {
    try { return readReducedTransparency(window.localStorage); } catch { return false; }
  });
  const [systemReducedTransparency, setSystemReducedTransparency] = useState(() => window.matchMedia(reducedTransparencyMediaQuery).matches);
  useEffect(() => {
    const media = window.matchMedia(reducedTransparencyMediaQuery);
    const update = () => setSystemReducedTransparency(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const [user, setUser] = useState<LauncherUser | null>(() => getDevelopmentPreviewUser());
  const [booting, setBooting] = useState(() => import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === 'boot');
  const [firstBoot, setFirstBoot] = useState(true);
  const accountEpoch = useRef(0);
  const renderedEpoch = accountEpoch.current;
  const completeBoot = useCallback(() => setBooting(false), []);

  const authenticated = (nextUser: LauncherUser) => {
    if (accountEpoch.current !== renderedEpoch) return;
    accountEpoch.current += 1;
    setUser(nextUser);
    if (nextUser.basicQuestionnaireCompletedAt) {
      setFirstBoot(false);
      setBooting(true);
      void import('./pages/LauncherHome').catch(() => undefined);
    }
  };

  const questionnaireCompleted = (nextUser: LauncherUser) => {
    if (accountEpoch.current !== renderedEpoch || nextUser.id !== user?.id) return;
    setUser(nextUser);
    setFirstBoot(true);
    setBooting(true);
    void import('./pages/LauncherHome').catch(() => undefined);
  };

  const logout = async () => {
    const epoch = ++accountEpoch.current;
    try {
      await signOut();
    } catch {
      // A failed bridge must not leave a signed-out renderer holding private UI.
    } finally {
      if (accountEpoch.current === epoch) {
        setBooting(false);
        setUser(null);
      }
    }
  };

  const userUpdated = (nextUser: LauncherUser) => {
    if (accountEpoch.current === renderedEpoch && nextUser.id === user?.id) setUser(nextUser);
  };

  if (booting && user?.basicQuestionnaireCompletedAt) return <BootSequence user={user} durationMs={firstBoot ? 2700 : 650} onComplete={completeBoot}/>;

  const content = !user
    ? <AuthScreen onAuthenticated={authenticated}/>
    : !user.basicQuestionnaireCompletedAt
      ? <QuestionnaireScreen user={user} onCompleted={questionnaireCompleted} onLogout={() => { void logout(); }}/>
      : <LauncherHome key={user.id} user={user} onLogout={() => { void logout(); }} onUserUpdated={userUpdated}/>;

  const toggleTransparency = () => {
    const next = !reducedTransparency;
    setReducedTransparency(next);
    try { saveReducedTransparency(window.localStorage, next); } catch { /* Storage may be unavailable. */ }
  };
  const effectiveReducedTransparency = reducedTransparency || systemReducedTransparency;
  return <div className={`app ui-refresh ui-glass${effectiveReducedTransparency ? ' ui-glass-reduced' : ''}`} style={getThemeStyle(user?.basicQuestionnaire?.favoriteColor)}><TitleBar canEnterCompanion={Boolean(user?.basicQuestionnaireCompletedAt)} reducedTransparency={effectiveReducedTransparency} systemReducedTransparency={systemReducedTransparency} onToggleTransparency={toggleTransparency}/>{content}</div>;
}

export default function App() {
  const companionMode = new URLSearchParams(window.location.search).get('mode') === 'companion';
  return <PageLoadBoundary>{companionMode ? <CompanionApp/> : <LauncherApplication/>}</PageLoadBoundary>;
}
