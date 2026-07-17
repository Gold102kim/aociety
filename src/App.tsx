import { useState } from 'react';
import { LauncherUser, signOut } from './auth';
import { TitleBar } from './components/LauncherUi';
import { getDevelopmentPreviewUser } from './dev/previewUser';
import { AuthScreen, QuestionnaireScreen } from './pages/AccountFlow';
import { BootSequence } from './pages/BootSequence';
import { CompanionApp } from './pages/CompanionApp';
import { LauncherHome } from './pages/LauncherHome';
import { getThemeStyle } from './theme';

function LauncherApplication() {
  const [user, setUser] = useState<LauncherUser | null>(() => getDevelopmentPreviewUser());
  const [booting, setBooting] = useState(() => import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === 'boot');

  const authenticated = (nextUser: LauncherUser) => {
    setUser(nextUser);
    if (nextUser.basicQuestionnaireCompletedAt) setBooting(true);
  };

  const questionnaireCompleted = (nextUser: LauncherUser) => {
    setUser(nextUser);
    setBooting(true);
  };

  const logout = async () => {
    try {
      await signOut();
    } finally {
      setBooting(false);
      setUser(null);
    }
  };

  if (booting && user?.basicQuestionnaireCompletedAt) return <BootSequence user={user} onComplete={() => setBooting(false)}/>;

  const content = !user
    ? <AuthScreen onAuthenticated={authenticated}/>
    : !user.basicQuestionnaireCompletedAt
      ? <QuestionnaireScreen user={user} onCompleted={questionnaireCompleted} onLogout={() => { void logout(); }}/>
      : <LauncherHome user={user} onLogout={() => { void logout(); }} onUserUpdated={setUser}/>;

  return <div className="app" style={getThemeStyle(user?.basicQuestionnaire?.favoriteColor)}><TitleBar canEnterCompanion={Boolean(user?.basicQuestionnaireCompletedAt)}/>{content}</div>;
}

export default function App() {
  const companionMode = new URLSearchParams(window.location.search).get('mode') === 'companion';
  return companionMode ? <CompanionApp/> : <LauncherApplication/>;
}
