import React, { useState, useEffect } from 'react';
import './styles/topaz.css';
import { AuthProvider, useAuth } from './AuthContext.jsx';
import { DecisionProvider } from './DecisionContext.jsx';
import Login from './pages/Login.jsx';
import Main from './pages/Main.jsx';
import Marketing from './pages/Marketing.jsx';
import Production from './pages/Production.jsx';
import Personnel from './pages/Personnel.jsx';
import Finance from './pages/Finance.jsx';
import Reports from './pages/Reports.jsx';
import Review from './pages/Review.jsx';
import Manual from './pages/Manual.jsx';
import AdminLogin from './pages/AdminLogin.jsx';
import AdminDashboard from './pages/AdminDashboard.jsx';

/* Tiny hash-based router (~30 lines). Hashes look like:
   #/main, #/reports, #/admin?view=audit */
function useHashRoute() {
  const parse = () => {
    const raw = window.location.hash.replace(/^#/, '') || '/';
    const [path, qs] = raw.split('?');
    return { path: path || '/', query: Object.fromEntries(new URLSearchParams(qs || '')) };
  };
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onChange = () => setRoute(parse());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}

function TeamShell({ children }) {
  // Loads the decision form once the team area is entered; server is the
  // source of truth, mirrored to localStorage.
  return <DecisionProvider>{children}</DecisionProvider>;
}

function Routes() {
  const { path, query } = useHashRoute();
  const { auth, adminAuth } = useAuth();

  if (path === '/admin-login') {
    if (adminAuth) {
      window.location.hash = '#/admin';
      return null;
    }
    return <AdminLogin />;
  }

  if (path === '/admin') {
    if (!adminAuth) {
      window.location.hash = '#/admin-login';
      return null;
    }
    return <AdminDashboard view={query.view} />;
  }

  // Team area
  if (!auth) {
    if (path !== '/') window.location.hash = '#/';
    return <Login />;
  }

  switch (path) {
    case '/':
      window.location.hash = '#/main';
      return null;
    case '/main':
      return <Main />;
    case '/marketing':
      return <TeamShell><Marketing /></TeamShell>;
    case '/production':
      return <TeamShell><Production /></TeamShell>;
    case '/personnel':
      return <TeamShell><Personnel /></TeamShell>;
    case '/finance':
      return <TeamShell><Finance /></TeamShell>;
    case '/reports':
      return <Reports />;
    case '/review':
      return <TeamShell><Review /></TeamShell>;
    case '/manual':
      return <Manual />;
    default:
      return (
        <div className="topaz-page">
          <h1>Topaz-Vbe — Virtual Business Environment</h1>
          <div className="error-list">Unknown page: {path}</div>
          <p><a href="#/main">Back to main</a></p>
        </div>
      );
  }
}

export default function App() {
  return (
    <AuthProvider>
      <Routes />
    </AuthProvider>
  );
}
