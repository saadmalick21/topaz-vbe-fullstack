import React, { useState, useEffect } from 'react';
import { getTables } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import DataTable from '../components/DataTable.jsx';
import { TEAM_LINKS } from './Main.jsx';
import { pretty } from '../format.js';

/* Generic renderer: tables arrive as { title, description, columns, rows }
   or as plain objects / arrays / strings — render whatever we get. */
function RenderTable({ name, t }) {
  if (t === null || t === undefined) return null;

  if (typeof t === 'string' || typeof t === 'number' || typeof t === 'boolean') {
    return (
      <div>
        <h3>{name}</h3>
        <p>{pretty(t)}</p>
      </div>
    );
  }

  if (Array.isArray(t)) {
    if (t.length > 0 && typeof t[0] === 'object' && !Array.isArray(t[0])) {
      const keys = [...new Set(t.flatMap((r) => Object.keys(r)))];
      const columns = keys.map((k) => ({
        key: k,
        label: k.replace(/_/g, ' '),
        align: typeof t[0][k] === 'number' ? 'right' : 'left',
      }));
      const rows = t.map((r) => {
        const row = {};
        keys.forEach((k) => {
          row[k] = typeof r[k] === 'object' && r[k] !== null ? JSON.stringify(r[k]) : pretty(r[k]);
        });
        return row;
      });
      return <DataTable title={name} columns={columns} rows={rows} />;
    }
    return (
      <div>
        <h3>{name}</h3>
        <ul>
          {t.map((v, i) => (
            <li key={i}>{pretty(v)}</li>
          ))}
        </ul>
      </div>
    );
  }

  // object
  const { title, description, columns, rows, ...rest } = t;
  const heading = title || name;
  if (columns && rows) {
    const cols = columns.map((c) =>
      typeof c === 'string' ? { key: c, label: c } : c
    );
    return (
      <div>
        <DataTable title={heading} columns={cols} rows={rows} />
        {description ? <p className="note">{description}</p> : null}
      </div>
    );
  }
  const entries = Object.entries(rest);
  if (entries.length === 0) return null;
  return (
    <div>
      <h3>{heading}</h3>
      {description ? <p className="note">{description}</p> : null}
      <div className="table-scroll">
        <table className="kv">
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k}>
                <th>{k.replace(/_/g, ' ')}</th>
                <td>{typeof v === 'object' && v !== null ? JSON.stringify(v) : pretty(v)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Manual() {
  const { auth, logout } = useAuth();
  const [tables, setTables] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getTables()
      .then((t) => {
        if (!cancelled) {
          setTables(t);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load the manual tables.');
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const names = tables ? Object.keys(tables) : [];

  return (
    <div className="topaz-page">
      <TopazHeader team={auth?.team} industry={auth?.industry} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/manual" />
      <h2>Operating Manual — Reference Tables</h2>
      <p className="note">
        This manual describes how the Virtual Business Environment works. You manage a
        manufacturing company competing against the other companies in your industry.
        Each quarter you complete the Decision Form (Marketing, Production, Personnel,
        Finance) and submit it before the deadline. All companies are then simulated
        together and your Management Report is published.
      </p>
      <p className="criterion">
        SHARE PRICE IS THE CRITERION BY WHICH PERFORMANCE IS JUDGED.
      </p>
      <p className="note">
        Money is shown in pounds (£). Decision-form labels marked (£'000) are entered
        in thousands of pounds. The tables below give the operating parameters used by
        the simulation.
      </p>
      <hr />

      {loading ? <p>Loading tables…</p> : null}
      {!loading && error ? <div className="error-list">{error}</div> : null}
      {!loading && !error && tables ? (
        <>
          <p className="note">
            Tables available:{' '}
            {names.map((n, i) => (
              <span key={n}>
                <a href={'#tbl-' + encodeURIComponent(n)}>{n}</a>
                {i < names.length - 1 ? ' · ' : ''}
              </span>
            ))}
          </p>
          {names.map((n) => (
            <div key={n} id={'tbl-' + n}>
              <RenderTable name={n} t={tables[n]} />
              <hr />
            </div>
          ))}
        </>
      ) : null}

      <div className="footer-note">Topaz-VBE replica — Edit 515 Virtual Business Environment</div>
    </div>
  );
}
