import React, { createContext, useContext, useState } from 'react';
import { logoutTeam, logoutAdmin } from './api.js';

const AuthContext = createContext(null);

function loadStored(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => loadStored('topaz_auth'));
  const [adminAuth, setAdminAuth] = useState(() => loadStored('topaz_admin_auth'));

  const login = (payload) => {
    // payload: { token, role, team, industry }
    const a = { role: payload.role, team: payload.team, industry: payload.industry };
    localStorage.setItem('topaz_auth', JSON.stringify(a));
    setAuth(a);
  };

  const adminLogin = (payload) => {
    // payload: { token, role }
    const a = { role: payload.role };
    localStorage.setItem('topaz_admin_auth', JSON.stringify(a));
    setAdminAuth(a);
  };

  const logout = () => {
    logoutTeam();
    setAuth(null);
    window.location.hash = '#/';
  };

  const adminLogout = () => {
    logoutAdmin();
    setAdminAuth(null);
    window.location.hash = '#/admin-login';
  };

  return (
    <AuthContext.Provider value={{ auth, adminAuth, login, adminLogin, logout, adminLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
