import React, { useState } from 'react';
import { loginTeam } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import { NumField, TextField } from '../components/Fields.jsx';

export default function Login() {
  const { login } = useAuth();
  const [simulationCode, setSimulationCode] = useState('');
  const [groupNumber, setGroupNumber] = useState('');
  const [companyNumber, setCompanyNumber] = useState('');
  const [identityNumber, setIdentityNumber] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const doLogin = async () => {
    setError('');
    setBusy(true);
    try {
      const res = await loginTeam({
        simulation_code: simulationCode.trim(),
        group_number: Number(groupNumber),
        company_number: Number(companyNumber),
        identity_number: identityNumber.trim(),
      });
      login(res);
      window.location.hash = '#/main';
    } catch (e) {
      setError(
        'Invalid team credentials — please check all four fields and try again.'
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="topaz-page">
      <h1 style={{ textAlign: 'center' }}>Topaz-Vbe — Virtual Business Environment</h1>
      <div className="login-box">
        <h2>Team Login</h2>
        <p className="note">
          Enter the four identifiers issued for your company. All four must match the
          records held for your simulation. The Identity Number is your company's
          secret credential — do not share it.
        </p>
        {error ? <div className="error-list">{error}</div> : null}
        <TextField label="Simulation Code" value={simulationCode} onChange={setSimulationCode} width={200} />
        <NumField label="Group Number" value={groupNumber} onChange={setGroupNumber} integers width={90} />
        <NumField label="Company Number" value={companyNumber} onChange={setCompanyNumber} integers width={90} />
        <TextField label="Identity Number" value={identityNumber} onChange={setIdentityNumber} width={200} />
        <div className="button-bar">
          <button onClick={doLogin} disabled={busy}>
            {busy ? 'Checking…' : 'Enter'}
          </button>
        </div>
        <p className="note">
          Demonstration industry: Simulation Code <b>TOPAZ-DEMO</b>, Group Number{' '}
          <b>1</b>, Company Number <b>1</b>–<b>4</b>, Identity Number <b>ID-1001</b>–
          <b>ID-1004</b>.
        </p>
        <hr />
        <p className="note">
          Administrators: <a href="#/admin-login">admin login</a>
        </p>
      </div>
      <div className="footer-note">
        Topaz-VBE replica — Edit 515 Virtual Business Environment
      </div>
    </div>
  );
}
