import React, { useState, useEffect } from 'react';
import {
  adminIndustries,
  adminCreateIndustry,
  adminIndustryDetail,
  adminCreateTeam,
  adminOpenQuarter,
  adminSetShock,
  adminRollStatus,
  adminRollQuarter,
  adminAuditLog,
} from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import DataTable from '../components/DataTable.jsx';
import ConfirmBox from '../components/ConfirmBox.jsx';
import { ErrorList } from '../components/ActionButtons.jsx';
import { NumField, TextField, CheckField } from '../components/Fields.jsx';
import { fmtDate, pretty, yesNo } from '../format.js';

const ADMIN_LINKS = [
  { to: '/admin', label: 'Industries' },
  { to: '/admin?view=audit', label: 'Audit Log' },
];

function IndustryDetail({ industryId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  // add-team form
  const [teamName, setTeamName] = useState('');
  const [teamGroup, setTeamGroup] = useState('');
  const [teamCompany, setTeamCompany] = useState('');
  const [newIdentity, setNewIdentity] = useState('');

  // open-quarter form
  const [qYear, setQYear] = useState(1);
  const [qQuarter, setQQuarter] = useState(1);
  const [qAutoPass, setQAutoPass] = useState(10080);

  // shock form
  const [sYear, setSYear] = useState(1);
  const [sQuarter, setSQuarter] = useState(1);
  const [inflation, setInflation] = useState('');
  const [matPrice, setMatPrice] = useState('');
  const [recession, setRecession] = useState(false);
  const [note, setNote] = useState('');

  // roll
  const [rollStatus, setRollStatus] = useState(null);
  const [force, setForce] = useState(false);
  const [confirmRoll, setConfirmRoll] = useState(false);
  const [rollResult, setRollResult] = useState(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const d = await adminIndustryDetail(industryId);
      setDetail(d);
    } catch (e) {
      setError('Could not load industry detail.');
    } finally {
      setLoading(false);
    }
  };

  const loadRollStatus = async () => {
    try {
      const rs = await adminRollStatus(industryId);
      setRollStatus(rs);
      setError('');
      return rs;
    } catch (e) {
      setError((e.body && e.body.error) || 'Could not load roll status.');
      return null;
    }
  };

  useEffect(() => {
    load();
    loadRollStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [industryId]);

  const doCreateTeam = async () => {
    setError('');
    setNotice('');
    setNewIdentity('');
    try {
      const t = await adminCreateTeam(industryId, {
        name: teamName.trim(),
        group_number: Number(teamGroup),
        company_number: Number(teamCompany),
      });
      setNewIdentity(t.identity_number);
      setNotice('Team created: ' + (t.name || 'Company ' + t.company_number));
      setTeamName('');
      setTeamGroup('');
      setTeamCompany('');
      load();
    } catch (e) {
      setError((e.body && (e.body.error || (e.body.errors || []).join(' '))) || 'Could not create team.');
    }
  };

  const doOpenQuarter = async () => {
    setError('');
    setNotice('');
    try {
      await adminOpenQuarter(industryId, {
        year: Number(qYear),
        quarter: Number(qQuarter),
        auto_pass_minutes: Number(qAutoPass),
      });
      setNotice('Quarter opened: Year ' + qYear + ', Quarter ' + qQuarter + '.');
      load();
      loadRollStatus();
    } catch (e) {
      setError((e.body && (e.body.error || (e.body.errors || []).join(' '))) || 'Could not open quarter.');
    }
  };

  const doSetShock = async () => {
    setError('');
    setNotice('');
    const body = { year: Number(sYear), quarter: Number(sQuarter) };
    if (inflation !== '') body.inflation_pct = Number(inflation);
    if (matPrice !== '') body.material_price_change_pct = Number(matPrice);
    body.recession = !!recession;
    if (note.trim() !== '') body.note = note.trim();
    try {
      await adminSetShock(industryId, body);
      setNotice('Economic shock saved for Year ' + sYear + ', Quarter ' + sQuarter + '.');
      load();
    } catch (e) {
      setError((e.body && (e.body.error || (e.body.errors || []).join(' '))) || 'Could not save shock.');
    }
  };

  const doRoll = async () => {
    setError('');
    setRollResult(null);
    try {
      const r = await adminRollQuarter(industryId, force);
      setRollResult(r);
      setNotice('');
      load();
      if (r && r.queued) {
        // Queue mode: the engine worker processes the job in the background.
        // Poll roll-status until the quarter is published or the job ends.
        setNotice('Quarter queued for the engine worker (job #' + (r.job && r.job.id) + '). Waiting for it to finish…');
        let tries = 0;
        const poll = async () => {
          tries += 1;
          const s = await loadRollStatus();
          const done = s && (s.status === 'published' ||
            (s.job && (s.job.status === 'done' || s.job.status === 'failed')));
          if (!done && tries < 40) {
            setTimeout(poll, 3000);
          } else if (s && s.job && s.job.status === 'failed') {
            setError('Engine worker failed: ' + (s.job.error || 'unknown error'));
            setNotice('');
          } else {
            setNotice('');
          }
          load();
        };
        setTimeout(poll, 3000);
      } else {
        loadRollStatus();
      }
    } catch (e) {
      const b = e.body || {};
      let msg = b.error || 'Roll failed.';
      if (b.missing && b.missing.length > 0) {
        msg += ' Not submitted: ' + b.missing.map((m) => 'Co. ' + m.company_number + ' (' + (m.name || '') + ')').join(', ') + '.';
      }
      setError(msg);
    }
  };

  if (loading) return <p>Loading industry…</p>;

  const industry = detail?.industry;
  const teams = detail?.teams || [];
  const qtrs = detail?.quarters || [];
  const macro = detail?.macro || [];

  return (
    <div>
      <p>
        <a href="#/admin" onClick={(e) => { e.preventDefault(); onBack(); }}>
          &laquo; Back to industries
        </a>
      </p>
      <h2>
        Industry: {industry?.name} [{industry?.simulation_code}]
      </h2>
      <ErrorList errors={error ? [error] : []} />
      {notice ? <div className="success-box">{notice}</div> : null}

      <h3>Teams</h3>
      <DataTable
        columns={[
          { key: 'group_number', label: 'Group', align: 'right' },
          { key: 'company_number', label: 'Company', align: 'right' },
          { key: 'name', label: 'Name' },
          { key: 'identity_number', label: 'Identity Number' },
          { key: 'active', label: 'Active', align: 'center' },
        ]}
        rows={teams.map((t) => ({ ...t, active: yesNo(t.active) }))}
      />
      <fieldset>
        <legend>Add Team</legend>
        <TextField label="Team (company) name" value={teamName} onChange={setTeamName} width={220} />
        <NumField label="Group Number" value={teamGroup} onChange={setTeamGroup} integers width={90} />
        <NumField label="Company Number" value={teamCompany} onChange={setTeamCompany} integers width={90} />
        <div className="button-bar">
          <button onClick={doCreateTeam}>Add team</button>
        </div>
        {newIdentity ? (
          <div className="success-box">
            Generated Identity Number: <b>{newIdentity}</b> — record it securely; it is the
            team's secret login credential.
          </div>
        ) : null}
      </fieldset>

      <h3>Quarters</h3>
      <DataTable
        columns={[
          { key: 'year', label: 'Year', align: 'right' },
          { key: 'quarter', label: 'Quarter', align: 'right' },
          { key: 'status', label: 'Status' },
          { key: 'deadline_at', label: 'Deadline' },
          { key: 'published_at', label: 'Published' },
        ]}
        rows={qtrs.map((q) => ({
          ...q,
          deadline_at: fmtDate(q.deadline_at),
          published_at: fmtDate(q.published_at),
        }))}
      />
      <fieldset>
        <legend>Open New Quarter</legend>
        <NumField label="Year" value={qYear} onChange={setQYear} integers width={90} />
        <NumField label="Quarter" value={qQuarter} onChange={setQQuarter} integers width={90} />
        <NumField
          label="Auto-pass minutes"
          value={qAutoPass}
          onChange={setQAutoPass}
          integers
          width={120}
        />
        <div className="button-bar">
          <button onClick={doOpenQuarter}>Open quarter</button>
        </div>
        <p className="note">The previous quarter must be published before a new one opens.</p>
      </fieldset>

      <h3>Economic Shocks</h3>
      <DataTable
        columns={[
          { key: 'year', label: 'Year', align: 'right' },
          { key: 'quarter', label: 'Quarter', align: 'right' },
          { key: 'inflation_pct', label: 'Inflation %', align: 'right' },
          { key: 'material_price_change_pct', label: 'Material price change %', align: 'right' },
          { key: 'recession', label: 'Recession', align: 'center' },
          { key: 'note', label: 'Note' },
        ]}
        rows={macro.map((m) => ({ ...m, recession: yesNo(m.recession) }))}
      />
      <fieldset>
        <legend>Set Shock (upsert by Year/Quarter)</legend>
        <NumField label="Year" value={sYear} onChange={setSYear} integers width={90} />
        <NumField label="Quarter" value={sQuarter} onChange={setSQuarter} integers width={90} />
        <NumField label="Inflation %" value={inflation} onChange={setInflation} width={90} />
        <NumField label="Material price change %" value={matPrice} onChange={setMatPrice} width={90} />
        <CheckField label="Recession" value={recession} onChange={setRecession} />
        <TextField label="Note" value={note} onChange={setNote} width={260} />
        <div className="button-bar">
          <button onClick={doSetShock}>Save shock</button>
        </div>
      </fieldset>

      <h3>Roll the Quarter</h3>
      <fieldset>
        <legend>Submission Checklist</legend>
        {rollStatus ? (
          <>
            <p className="note">
              Year <b>{rollStatus.year}</b>, Quarter <b>{rollStatus.quarter}</b> — status{' '}
              <b>{rollStatus.status}</b> · Deadline:{' '}
              {fmtDate(rollStatus.deadline_at)} · All submitted:{' '}
              <b>{yesNo(rollStatus.all_submitted)}</b> · Deadline passed:{' '}
              <b>{yesNo(rollStatus.deadline_passed)}</b>
              {rollStatus.job ? (
                <span> · Worker job <b>#{rollStatus.job.id}</b>: <b>{rollStatus.job.status}</b></span>
              ) : null}
            </p>
            <DataTable
              columns={[
                { key: 'company_number', label: 'Company', align: 'right' },
                { key: 'name', label: 'Name' },
                { key: 'submitted', label: 'Submitted', align: 'center' },
                { key: 'submitted_at', label: 'Submitted at' },
              ]}
              rows={(rollStatus.teams || []).map((t) => ({
                ...t,
                submitted: yesNo(t.submitted),
                submitted_at: fmtDate(t.submitted_at),
              }))}
            />
          </>
        ) : (
          <p className="note">Loading roll status…</p>
        )}
        <CheckField
          label="Force roll (process even if not all teams submitted and the deadline has not passed)"
          value={force}
          onChange={setForce}
        />
        <div className="button-bar">
          <button onClick={() => setConfirmRoll(true)}>Roll the Quarter</button>{' '}
          <button onClick={loadRollStatus}>Refresh checklist</button>
        </div>
        {rollResult && rollResult.queued ? (
          <div className="success-box">
            Quarter queued for the engine worker (job #{rollResult.job && rollResult.job.id},{' '}
            status: {rollResult.job && rollResult.job.status}). The worker will simulate Year{' '}
            {rollResult.summary.year}, Quarter {rollResult.summary.quarter} and publish the reports.
            Auto-passed: {(rollResult.summary.auto_passed || []).join(', ') || 'none'}.
          </div>
        ) : null}
        {rollResult && rollResult.summary && !rollResult.queued ? (
          <div className="success-box">
            Quarter rolled: Year {rollResult.summary.year}, Quarter{' '}
            {rollResult.summary.quarter}. Teams processed:{' '}
            {rollResult.summary.teams_processed}. Auto-passed:{' '}
            {(rollResult.summary.auto_passed || []).join(', ') || 'none'}. Published at{' '}
            {fmtDate(rollResult.summary.published_at)}.
          </div>
        ) : null}
      </fieldset>
      <ConfirmBox
        open={confirmRoll}
        message={
          'Roll Year ' + (rollStatus?.year ?? '?') + ', Quarter ' + (rollStatus?.quarter ?? '?') +
          ' through processing? This simulates the quarter for ALL teams and publishes the reports.' +
          (force ? ' FORCE is set: unsubmitted teams will auto-pass.' : '')
        }
        confirmLabel="Roll the Quarter"
        onConfirm={() => {
          setConfirmRoll(false);
          doRoll();
        }}
        onCancel={() => setConfirmRoll(false)}
      />
    </div>
  );
}

export default function AdminDashboard({ view }) {
  const { adminLogout } = useAuth();
  const [industries, setIndustries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState(null);

  // create-industry form
  const [indName, setIndName] = useState('');
  const [simCode, setSimCode] = useState('');

  // audit log
  const [audit, setAudit] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);

  const loadIndustries = async () => {
    setLoading(true);
    setError('');
    try {
      const list = await adminIndustries();
      setIndustries(list || []);
    } catch (e) {
      setError('Could not load industries.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIndustries();
  }, []);

  useEffect(() => {
    if (view === 'audit') {
      setAuditLoading(true);
      adminAuditLog()
        .then((rows) => setAudit(rows || []))
        .catch(() => setError('Could not load audit log.'))
        .finally(() => setAuditLoading(false));
    }
  }, [view]);

  const doCreateIndustry = async () => {
    setError('');
    setNotice('');
    try {
      const ind = await adminCreateIndustry({
        name: indName.trim(),
        simulation_code: simCode.trim(),
      });
      setNotice('Industry created: ' + ind.name + ' [' + ind.simulation_code + '].');
      setIndName('');
      setSimCode('');
      loadIndustries();
    } catch (e) {
      setError((e.body && (e.body.error || (e.body.errors || []).join(' '))) || 'Could not create industry.');
    }
  };

  return (
    <div className="topaz-page">
      <TopazHeader admin onLogout={adminLogout} />
      <ClassicNav links={ADMIN_LINKS} current={view === 'audit' ? '/admin?view=audit' : '/admin'} />
      <h2>Industry Administration</h2>
      <ErrorList errors={error ? [error] : []} />
      {notice ? <div className="success-box">{notice}</div> : null}

      {view === 'audit' ? (
        <div>
          <h3>Audit Log</h3>
          {auditLoading ? <p>Loading…</p> : null}
          <DataTable
            columns={[
              { key: 'id', label: 'ID', align: 'right' },
              { key: 'created_at', label: 'When' },
              { key: 'industry_id', label: 'Industry', align: 'right' },
              { key: 'actor', label: 'Actor' },
              { key: 'action', label: 'Action' },
              { key: 'details', label: 'Details' },
            ]}
            rows={audit.map((a) => ({
              ...a,
              created_at: fmtDate(a.created_at),
              details: typeof a.details === 'object' && a.details !== null ? JSON.stringify(a.details) : pretty(a.details),
            }))}
          />
        </div>
      ) : selected ? (
        <IndustryDetail industryId={selected} onBack={() => { setSelected(null); loadIndustries(); }} />
      ) : (
        <div>
          <h3>Industries</h3>
          {loading ? <p>Loading…</p> : null}
          <DataTable
            columns={[
              { key: 'id', label: 'ID', align: 'right' },
              { key: 'name', label: 'Name' },
              { key: 'simulation_code', label: 'Simulation Code' },
              { key: 'status', label: 'Status' },
              { key: 'team_count', label: 'Teams', align: 'right' },
              { key: 'current_quarter', label: 'Current Quarter' },
              { key: 'open', label: '', align: 'center' },
            ]}
            rows={industries.map((i) => ({
              ...i,
              current_quarter: i.current_quarter
                ? 'Y' + i.current_quarter.year + ' Q' + i.current_quarter.quarter + ' (' + i.current_quarter.status + ')'
                : '—',
              open: (
                <button onClick={() => setSelected(i.id)}>Manage</button>
              ),
            }))}
          />
          <fieldset>
            <legend>Create Industry</legend>
            <TextField label="Industry name" value={indName} onChange={setIndName} width={220} />
            <TextField label="Simulation Code" value={simCode} onChange={setSimCode} width={220} />
            <div className="button-bar">
              <button onClick={doCreateIndustry}>Create industry</button>
            </div>
          </fieldset>
        </div>
      )}

      <div className="footer-note">Topaz-VBE replica — Edit 515 Virtual Business Environment</div>
    </div>
  );
}
