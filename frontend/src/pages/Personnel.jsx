import React, { useEffect } from 'react';
import { useAuth } from '../AuthContext.jsx';
import { useDecisions } from '../DecisionContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import ActionButtons from '../components/ActionButtons.jsx';
import DataTable from '../components/DataTable.jsx';
import { NumField } from '../components/Fields.jsx';
import { TEAM_LINKS } from './Main.jsx';
import { useLastPublishedReport } from '../reportUtil.js';
import { num } from '../format.js';

export default function Personnel() {
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
  const res = lastReport.report?.resources;

  const staffRows = [
    {
      category: 'Salespeople',
      current: '—',
      recruit: data.salespeople_changes?.recruit ?? 0,
      dismiss: data.salespeople_changes?.dismiss ?? 0,
      train: data.salespeople_changes?.train ?? 0,
      note: 'Recruit/dismiss/train this quarter',
    },
    {
      category: 'Assembly workers',
      current: res?.assembly?.workers != null ? num(res.assembly.workers) : '—',
      recruit: data.assembly_changes?.recruit ?? 0,
      dismiss: data.assembly_changes?.dismiss ?? 0,
      train: data.assembly_changes?.train ?? 0,
      note:
        res?.assembly?.workers != null
          ? 'Projected: ' +
            num(res.assembly.workers + (data.assembly_changes?.recruit ?? 0) - (data.assembly_changes?.dismiss ?? 0))
          : '—',
    },
    {
      category: 'Machinists',
      current: res?.machines?.machinists != null ? num(res.machines.machinists) : '—',
      recruit: '—',
      dismiss: '—',
      train: '—',
      note: 'Hired automatically with shift level',
    },
  ];

  return (
    <div className="topaz-page">
      <TopazHeader team={auth?.team} industry={auth?.industry} quarter={year ? { year, quarter, status: submitted ? 'submitted' : 'open' } : null} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/personnel" />
      <h2>Personnel Decisions</h2>
      {submitted ? (
        <div className="info-box">
          Decisions for this quarter have been submitted — the form is locked until the
          quarter is processed.
        </div>
      ) : null}

      <fieldset>
        <legend>Staff — Current vs Proposed Changes</legend>
        {lastReport.loading ? (
          <p className="note">Loading last published report…</p>
        ) : null}
        {!lastReport.loading && !lastReport.report ? (
          <p className="note">
            No published Management Report yet — current staff figures will appear here
            after the first quarter is processed.
          </p>
        ) : null}
        {lastReport.report ? (
          <p className="note">
            Current figures from the last published report: Year {lastReport.quarter.year},
            Quarter {lastReport.quarter.quarter}.
          </p>
        ) : null}
        <DataTable
          columns={[
            { key: 'category', label: 'Category' },
            { key: 'current', label: 'Current (last report)', align: 'right' },
            { key: 'recruit', label: 'Recruit', align: 'right' },
            { key: 'dismiss', label: 'Dismiss', align: 'right' },
            { key: 'train', label: 'Train', align: 'right' },
            { key: 'note', label: 'Note' },
          ]}
          rows={staffRows}
        />
      </fieldset>

      <fieldset>
        <legend>Salespeople — Recruit / Dismiss / Train</legend>
        <NumField
          label="Recruit"
          value={data.salespeople_changes?.recruit}
          onChange={(v) => set(['salespeople_changes', 'recruit'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="Dismiss"
          value={data.salespeople_changes?.dismiss}
          onChange={(v) => set(['salespeople_changes', 'dismiss'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="Train"
          value={data.salespeople_changes?.train}
          onChange={(v) => set(['salespeople_changes', 'train'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <p className="note">
          Personnel department costs per salesperson: recruit £1,500 · dismiss £5,000 ·
          train £6,000.
        </p>
      </fieldset>

      <fieldset>
        <legend>Assembly Workers — Recruit / Dismiss / Train</legend>
        <NumField
          label="Recruit"
          value={data.assembly_changes?.recruit}
          onChange={(v) => set(['assembly_changes', 'recruit'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="Dismiss"
          value={data.assembly_changes?.dismiss}
          onChange={(v) => set(['assembly_changes', 'dismiss'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="Train"
          value={data.assembly_changes?.train}
          onChange={(v) => set(['assembly_changes', 'train'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <p className="note">
          Personnel department costs per assembly worker: recruit £1,200 · dismiss
          £3,000 · train £4,500.
        </p>
      </fieldset>

      <fieldset>
        <legend>Assembly Wage Rate</legend>
        <NumField
          label="Pounds per hour"
          value={data.assembly_wage?.pounds}
          onChange={(v) => set(['assembly_wage', 'pounds'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="Pence per hour"
          value={data.assembly_wage?.pence}
          onChange={(v) => set(['assembly_wage', 'pence'], v)}
          min={0}
          max={99}
          integers
          disabled={dis}
        />
        <p className="note">Minimum assembly wage is £8.50 per hour.</p>
      </fieldset>

      <fieldset>
        <legend>Salesperson Remuneration</legend>
        <NumField
          label="Quarterly salary"
          suffix="£'000"
          value={data.sales_remuneration?.quarterly_salary_000}
          onChange={(v) => set(['sales_remuneration', 'quarterly_salary_000'], v)}
          min={0}
          disabled={dis}
        />
        <NumField
          label="Commission on sales"
          suffix="%"
          value={data.sales_remuneration?.commission_pct}
          onChange={(v) => set(['sales_remuneration', 'commission_pct'], v)}
          min={0}
          max={100}
          disabled={dis}
        />
        <p className="note">Minimum quarterly salary is £2,000 (£'000 2.0).</p>
      </fieldset>

      <ActionButtons />
      <div className="footer-note">Topaz-VBE replica — Edit 515 Virtual Business Environment</div>
    </div>
  );
}
