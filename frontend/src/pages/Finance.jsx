import React, { useEffect } from 'react';
import { useAuth } from '../AuthContext.jsx';
import { useDecisions } from '../DecisionContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import ActionButtons from '../components/ActionButtons.jsx';
import { NumField, CheckField } from '../components/Fields.jsx';
import { TEAM_LINKS } from './Main.jsx';
import { useLastPublishedReport, ownCompany } from '../reportUtil.js';
import { gbp, gbp2 } from '../format.js';

export default function Finance() {
  const { auth, logout } = useAuth();
  const { data, set, submitted, loading, refresh, year, quarter } = useDecisions();
  const lastReport = useLastPublishedReport();

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (loading || !data) {
    return (
      <div className="topaz-page">
        <p>Loading decision form…</p>
      </div>
    );
  }

  const dis = submitted;
  const bs = lastReport.report?.balance_sheet;
  const own = ownCompany(lastReport.report);

  return (
    <div className="topaz-page">
      <TopazHeader team={auth?.team} industry={auth?.industry} quarter={year ? { year, quarter, status: submitted ? 'submitted' : 'open' } : null} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/finance" />
      <h2>Finance Decisions</h2>
      {submitted ? (
        <div className="info-box">
          Decisions for this quarter have been submitted — the form is locked until the
          quarter is processed.
        </div>
      ) : null}

      <fieldset>
        <legend>Current Financial Position</legend>
        {lastReport.loading ? <p className="note">Loading last published report…</p> : null}
        {!lastReport.loading && !lastReport.report ? (
          <p className="note">
            No published Management Report yet — the financial position will appear here
            after the first quarter is processed.
          </p>
        ) : null}
        {lastReport.report ? (
          <>
            <p className="note">
              From the last published report: Year {lastReport.quarter.year}, Quarter{' '}
              {lastReport.quarter.quarter}.
            </p>
            <table className="kv">
              <tbody>
                <tr>
                  <th>Cash invested</th>
                  <td>{gbp(bs?.cash_invested)}</td>
                </tr>
                <tr>
                  <th>Bank overdraft</th>
                  <td>{gbp(bs?.bank_overdraft)}</td>
                </tr>
                <tr>
                  <th>Overdraft limit</th>
                  <td>{gbp(bs?.overdraft_limit)}</td>
                </tr>
                <tr>
                  <th>Share price</th>
                  <td>{own?.share_price != null ? gbp2(own.share_price) : '—'}</td>
                </tr>
                <tr>
                  <th>Net worth</th>
                  <td>{gbp(bs?.net_worth)}</td>
                </tr>
              </tbody>
            </table>
          </>
        ) : null}
      </fieldset>

      <fieldset>
        <legend>Dividend and Credit Policy</legend>
        <NumField
          label="Dividend rate"
          suffix="pence per share"
          value={data.dividend_rate_pence}
          onChange={(v) => set(['dividend_rate_pence'], v)}
          min={0}
          disabled={dis}
        />
        <NumField
          label="Days credit allowed to customers"
          value={data.days_credit_allowed}
          onChange={(v) => set(['days_credit_allowed'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <p className="note">
          Credit discount: up to 7 days 10% · 8–15 days 7.5% · 16–29 days 5% · 30 days or
          more nil.
        </p>
      </fieldset>

      <fieldset>
        <legend>Information Wanted</legend>
        <CheckField
          label="Competitor information"
          note="£5,000 charged this quarter"
          value={data.info_wanted?.other_companies}
          onChange={(v) => set(['info_wanted', 'other_companies'], v)}
          disabled={dis}
        />
        <CheckField
          label="Market share information"
          note="£5,000 charged this quarter"
          value={data.info_wanted?.market_shares}
          onChange={(v) => set(['info_wanted', 'market_shares'], v)}
          disabled={dis}
        />
      </fieldset>

      <fieldset>
        <legend>Budgets</legend>
        <NumField
          label="Management budget"
          suffix="£'000"
          value={data.management_budget_000}
          onChange={(v) => set(['management_budget_000'], v)}
          min={0}
          disabled={dis}
        />
        <NumField
          label="Research expenditure"
          suffix="£'000"
          value={data.research_expenditure_000}
          onChange={(v) => set(['research_expenditure_000'], v)}
          min={0}
          disabled={dis}
        />
        <p className="note">Minimum management budget is £40,000 (£'000 40.0).</p>
      </fieldset>

      <ActionButtons />
      <div className="footer-note">Topaz-VBE replica — Edit 515 Virtual Business Environment</div>
    </div>
  );
}
