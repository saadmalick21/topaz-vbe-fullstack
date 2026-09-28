import React, { useState, useEffect } from 'react';
import { me } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import { fmtDate } from '../format.js';

export const TEAM_LINKS = [
  { to: '/main', label: 'Main' },
  { to: '/marketing', label: 'Marketing' },
  { to: '/production', label: 'Production' },
  { to: '/personnel', label: 'Personnel' },
  { to: '/finance', label: 'Finance' },
  { to: '/reports', label: 'Reports' },
  { to: '/review', label: 'Review' },
  { to: '/manual', label: 'Manual' },
];

export default function Main() {
  const { auth, logout } = useAuth();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    me()
      .then((res) => {
        if (!cancelled) setInfo(res);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load company information.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const team = auth?.team;
  const industry = auth?.industry;
  const q = info?.current_quarter;

  return (
    <div className="topaz-page">
      <TopazHeader team={team} industry={industry} quarter={q} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/main" />
      {error ? <div className="error-list">{error}</div> : null}

      <fieldset>
        <legend>Company Information</legend>
        <table className="kv">
          <tbody>
            <tr>
              <th>Company name</th>
              <td>{team?.name || 'Company ' + team?.company_number}</td>
            </tr>
            <tr>
              <th>Group Number</th>
              <td>{team?.group_number}</td>
            </tr>
            <tr>
              <th>Company Number</th>
              <td>{team?.company_number}</td>
            </tr>
            <tr>
              <th>Industry</th>
              <td>{industry?.name}</td>
            </tr>
            <tr>
              <th>Simulation Code</th>
              <td>{industry?.simulation_code}</td>
            </tr>
          </tbody>
        </table>
      </fieldset>

      <fieldset>
        <legend>Current Quarter Status</legend>
        {q ? (
          <table className="kv">
            <tbody>
              <tr>
                <th>Year</th>
                <td>{q.year}</td>
              </tr>
              <tr>
                <th>Quarter</th>
                <td>{q.quarter}</td>
              </tr>
              <tr>
                <th>Status</th>
                <td>
                  <b>{String(q.status).toUpperCase()}</b>
                </td>
              </tr>
              <tr>
                <th>Deadline</th>
                <td>{q.deadline_at ? fmtDate(q.deadline_at) : '—'}</td>
              </tr>
              <tr>
                <th>Your decisions</th>
                <td>{info?.submitted ? 'SUBMITTED (locked)' : 'Not yet submitted'}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="note">Loading quarter status…</p>
        )}
        <p className="note">
          Enter your decisions under Marketing, Production, Personnel and Finance while
          the quarter is open, then Submit them. When every company has submitted (or
          the deadline passes), the quarter is processed and your Management Report is
          published under Reports.
        </p>
      </fieldset>

      <p className="criterion">
        SHARE PRICE IS THE CRITERION BY WHICH PERFORMANCE IS JUDGED.
      </p>

      <div className="footer-note">
        Topaz-VBE replica — Edit 515 Virtual Business Environment
      </div>
    </div>
  );
}
