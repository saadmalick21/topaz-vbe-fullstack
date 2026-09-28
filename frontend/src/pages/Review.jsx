import React, { useEffect } from 'react';
import { useAuth } from '../AuthContext.jsx';
import { useDecisions } from '../DecisionContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import ActionButtons from '../components/ActionButtons.jsx';
import DecisionSummary from '../components/DecisionSummary.jsx';
import { TEAM_LINKS } from './Main.jsx';
import { fmtDate } from '../format.js';

export default function Review() {
  const { auth, logout } = useAuth();
  const { data, submitted, submittedAt, loading, refresh, year, quarter, confirmation } =
    useDecisions();

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="topaz-page">
      <TopazHeader team={auth?.team} industry={auth?.industry} quarter={year ? { year, quarter, status: submitted ? 'submitted' : 'open' } : null} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/review" />
      <h2>Review Decision Form</h2>

      {loading || !data ? (
        <p>Loading decision form…</p>
      ) : (
        <>
          {submitted ? (
            <div className="success-box">
              Decisions submitted
              {submittedAt ? ' at ' + fmtDate(submittedAt) : ''}. The form is LOCKED —
              awaiting quarter processing. The Management Report will appear under
              Reports when the quarter is published.
            </div>
          ) : (
            <p className="note">
              Read-only summary of your current decision form for Year {year}, Quarter{' '}
              {quarter}. Use the section pages to change values, Save the draft, then
              Submit when final.
            </p>
          )}
          <DecisionSummary data={data} />
          <ActionButtons showSubmit={!submitted} reviewLink={false} />
        </>
      )}

      <div className="footer-note">Topaz-VBE replica — Edit 515 Virtual Business Environment</div>
    </div>
  );
}
