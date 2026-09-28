import React, { useState } from 'react';
import { loginAdmin } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import { TextField } from '../components/Fields.jsx';

export default function AdminLogin() {
  const { adminLogin } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const doLogin = async () => {
    setError('');
    setBusy(true);
    try {
      const res = await loginAdmin({ username: username.trim(), password });
      adminLogin(res);
      window.location.hash = '#/admin';
    } catch (e) {
      setError('Invalid administrator credentials.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="topaz-page">
      <h1 style={{ textAlign: 'center' }}>Topaz-Vbe — Virtual Business Environment</h1>
      <div className="login-box">
        <h2>Administrator Login</h2>
        <p className="note">
          Industry administration: create industries and teams, open quarters, set
          economic shocks, and roll quarters through processing.
        </p>
        {error ? <div className="error-list">{error}</div> : null}
        <TextField label="Username" value={username} onChange={setUsername} width={200} />
        <TextField label="Password" value={password} onChange={setPassword} width={200} password />
        <div className="button-bar">
          <button onClick={doLogin} disabled={busy}>
            {busy ? 'Checking…' : 'Enter'}
          </button>
        </div>
        <hr />
        <p className="note">
          <a href="#/">Team login</a>
        </p>
      </div>
      <div className="footer-note">
        Topaz-VBE replica — Edit 515 Virtual Business Environment
      </div>
    </div>
  );
}
