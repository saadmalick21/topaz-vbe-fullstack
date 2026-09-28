import React, { useEffect } from 'react';
import { useAuth } from '../AuthContext.jsx';
import { useDecisions } from '../DecisionContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import ActionButtons from '../components/ActionButtons.jsx';
import { NumField, CellInput, CellCheck } from '../components/Fields.jsx';
import { TEAM_LINKS } from './Main.jsx';
import { AREAS, AREA_LABELS } from '../components/DecisionSummary.jsx';

export default function Marketing() {
  const { auth, logout } = useAuth();
  const { data, set, submitted, loading, refresh, year, quarter } = useDecisions();

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

  // set a value inside an array field, e.g. setIdx(['prices','export'], 1, 130)
  const setIdx = (path, i, v) => {
    const cur = path.reduce((o, k) => (o == null ? o : o[k]), data) || [];
    const next = cur.slice();
    next[i] = v;
    set(path, next);
  };

  return (
    <div className="topaz-page">
      <TopazHeader team={auth?.team} industry={auth?.industry} quarter={year ? { year, quarter, status: submitted ? 'submitted' : 'open' } : null} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/marketing" />
      <h2>Marketing Decisions</h2>
      {submitted ? (
        <div className="info-box">
          Decisions for this quarter have been submitted — the form is locked until the
          quarter is processed.
        </div>
      ) : null}

      <fieldset>
        <legend>Prices and Product Improvements</legend>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Product</th>
                <th className="num">Export price (£/unit)</th>
                <th className="num">Home price (£/unit)</th>
                <th className="center">Product improvement</th>
              </tr>
            </thead>
            <tbody>
              {[0, 1, 2].map((i) => (
                <tr key={i}>
                  <td>Product {i + 1}</td>
                  <td className="num">
                    <CellInput
                      value={data.prices?.export?.[i]}
                      onChange={(v) => setIdx(['prices', 'export'], i, v)}
                      disabled={dis}
                    />
                  </td>
                  <td className="num">
                    <CellInput
                      value={data.prices?.home?.[i]}
                      onChange={(v) => setIdx(['prices', 'home'], i, v)}
                      disabled={dis}
                    />
                  </td>
                  <td className="center">
                    <CellCheck
                      value={data.product_improvements?.[i]}
                      onChange={(v) => setIdx(['product_improvements'], i, v)}
                      disabled={dis}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          Prices must be greater than 0. Tick "Product improvement" to launch a major
          improvement for that product this quarter.
        </p>
      </fieldset>

      <fieldset>
        <legend>Promotion Expenditure (£'000 per product)</legend>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Product</th>
                <th className="num">Trade press</th>
                <th className="num">Advertising</th>
                <th className="num">Support</th>
                <th className="num">Merchandising</th>
              </tr>
            </thead>
            <tbody>
              {[0, 1, 2].map((i) => (
                <tr key={i}>
                  <td>Product {i + 1}</td>
                  <td className="num">
                    <CellInput
                      value={data.promotion?.trade_press?.[i]}
                      onChange={(v) => setIdx(['promotion', 'trade_press'], i, v)}
                      disabled={dis}
                    />
                  </td>
                  <td className="num">
                    <CellInput
                      value={data.promotion?.advertising?.[i]}
                      onChange={(v) => setIdx(['promotion', 'advertising'], i, v)}
                      disabled={dis}
                    />
                  </td>
                  <td className="num">
                    <CellInput
                      value={data.promotion?.support?.[i]}
                      onChange={(v) => setIdx(['promotion', 'support'], i, v)}
                      disabled={dis}
                    />
                  </td>
                  <td className="num">
                    <CellInput
                      value={data.promotion?.merchandising?.[i]}
                      onChange={(v) => setIdx(['promotion', 'merchandising'], i, v)}
                      disabled={dis}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </fieldset>

      <fieldset>
        <legend>Salespeople by Area</legend>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Area</th>
                <th className="num">Salespeople allocated</th>
              </tr>
            </thead>
            <tbody>
              {AREAS.map((a) => (
                <tr key={a}>
                  <td>{AREA_LABELS[a]}</td>
                  <td className="num">
                    <CellInput
                      value={data.salespeople?.[a]}
                      onChange={(v) => set(['salespeople', a], v)}
                      disabled={dis}
                      integers
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </fieldset>

      <fieldset>
        <legend>Sales Force Remuneration</legend>
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
