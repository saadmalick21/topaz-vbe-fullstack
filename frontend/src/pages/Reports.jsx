import React, { useState, useEffect } from 'react';
import { quarters, getReport } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import DataTable from '../components/DataTable.jsx';
import DecisionSummary, { AREA_LABELS } from '../components/DecisionSummary.jsx';
import { TEAM_LINKS } from './Main.jsx';
import { gbp, gbp2, num, pct, yesNo, fmtDate, pretty } from '../format.js';

/* Label/value table for report money sections. */
function KV({ title, obj, money }) {
  if (!obj || typeof obj !== 'object') return null;
  const rows = Object.entries(obj).map(([k, v]) => ({
    label: k.replace(/_/g, ' '),
    value: money ? gbp(v) : pretty(v),
  }));
  return (
    <div>
      {title ? <h3>{title}</h3> : null}
      <div className="table-scroll">
        <table className="kv">
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <th>{r.label}</th>
                <td>{r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Section({ report }) {
  if (!report) return null;
  const meta = report.meta || {};
  const res = report.resources || {};
  const products = report.products || [];
  const group = report.group || {};
  const economic = report.economic || {};
  const companies = group.companies || [];
  const shares = group.market_shares || {};

  const productRows = products.map((p) => ({
    product: 'P' + p.product,
    area: AREA_LABELS[p.area] || p.area,
    scheduled: num(p.scheduled),
    produced: num(p.produced),
    rejected: num(p.rejected),
    demand: num(p.demand),
    sales: num(p.sales),
    backlog: num(p.backlog),
    closing_stock: num(p.closing_stock),
    price: p.price != null ? gbp2(p.price) : '—',
    improvement: yesNo(p.improvement),
  }));

  const companyRows = companies.map((c) => ({
    company_number: c.company_number,
    company_name: c.company_name,
    share_price: c.share_price != null ? gbp2(c.share_price) : '—',
    dividend_pct: c.dividend_pct != null ? pct(c.dividend_pct) : '—',
    net_profit: gbp(c.net_profit),
    net_worth: gbp(c.net_worth),
  }));

  return (
    <div>
      <fieldset>
        <legend>Report Identification</legend>
        <table className="kv">
          <tbody>
            <tr><th>Industry</th><td>{meta.simulation_code}</td></tr>
            <tr><th>Group Number</th><td>{meta.group_number}</td></tr>
            <tr><th>Company Number</th><td>{meta.company_number}</td></tr>
            <tr><th>Company name</th><td>{meta.company_name}</td></tr>
            <tr><th>Year / Quarter</th><td>{meta.year} / {meta.quarter}</td></tr>
            <tr><th>Published</th><td>{fmtDate(meta.published_at)}</td></tr>
            <tr><th>Auto-pass</th><td>{yesNo(meta.auto_pass)}</td></tr>
            {meta.demo_data ? (
              <tr><th>Data</th><td><b>DEMONSTRATION DATA</b></td></tr>
            ) : null}
          </tbody>
        </table>
      </fieldset>

      <h2>Decisions Made</h2>
      <DecisionSummary data={report.decisions} />

      <h2>Resources Employed</h2>
      {res.machines ? (
        <KV title="Machines" obj={{
          'Machines owned': num(res.machines.owned),
          'New machines installed': num(res.machines.new_installed),
          'Machines sold': num(res.machines.sold),
          'Machine hours available': num(res.machines.hours_available),
          'Machine hours used': num(res.machines.hours_used),
          'Utilisation': res.machines.utilisation_pct != null ? pct(res.machines.utilisation_pct) : '—',
          'Machinists employed': num(res.machines.machinists),
        }} />
      ) : null}
      {res.assembly ? (
        <KV title="Assembly" obj={{
          'Assembly workers': num(res.assembly.workers),
          'Hours available': num(res.assembly.hours_available),
          'Hours used': num(res.assembly.hours_used),
          'Utilisation': res.assembly.utilisation_pct != null ? pct(res.assembly.utilisation_pct) : '—',
          'Wage rate': res.assembly.wage_rate != null ? gbp2(res.assembly.wage_rate) + '/hr' : '—',
        }} />
      ) : null}
      {res.vehicles ? (
        <KV title="Vehicles" obj={{
          'Vehicles owned': num(res.vehicles.owned),
          'Bought': num(res.vehicles.bought),
          'Sold': num(res.vehicles.sold),
        }} />
      ) : null}
      {res.materials ? (
        <KV title="Materials" obj={{
          'Opening stock (units)': num(res.materials.opening_stock),
          'Ordered (units)': num(res.materials.ordered),
          'Delivered (units)': num(res.materials.delivered),
          'Used (units)': num(res.materials.used),
          'Closing stock (units)': num(res.materials.closing_stock),
          'Price per 1000 units': res.materials.price_per_1000 != null ? gbp(res.materials.price_per_1000) : '—',
        }} />
      ) : null}

      <h2>Product Statistics</h2>
      <DataTable
        columns={[
          { key: 'product', label: 'Prod' },
          { key: 'area', label: 'Area' },
          { key: 'scheduled', label: 'Scheduled', align: 'right' },
          { key: 'produced', label: 'Produced', align: 'right' },
          { key: 'rejected', label: 'Rejected', align: 'right' },
          { key: 'demand', label: 'Demand', align: 'right' },
          { key: 'sales', label: 'Sales', align: 'right' },
          { key: 'backlog', label: 'Backlog', align: 'right' },
          { key: 'closing_stock', label: 'Closing stock', align: 'right' },
          { key: 'price', label: 'Price', align: 'right' },
          { key: 'improvement', label: 'Improved', align: 'center' },
        ]}
        rows={productRows}
      />

      <h2>Overheads</h2>
      <KV obj={report.overheads} money />

      <h2>Profit and Loss Account</h2>
      <KV obj={report.pnl} money />

      <h2>Balance Sheet</h2>
      <KV obj={report.balance_sheet} money />

      <h2>Cash Flow</h2>
      <KV obj={report.cash_flow} money />

      <h2>Group and Competitor Information</h2>
      <DataTable
        title="Companies in the industry"
        columns={[
          { key: 'company_number', label: 'Co.', align: 'right' },
          { key: 'company_name', label: 'Company' },
          { key: 'share_price', label: 'Share price', align: 'right' },
          { key: 'dividend_pct', label: 'Dividend %', align: 'right' },
          { key: 'net_profit', label: 'Net profit', align: 'right' },
          { key: 'net_worth', label: 'Net worth', align: 'right' },
        ]}
        rows={companyRows}
      />
      {Object.keys(shares).map((area) => {
        const byProduct = shares[area] || {};
        const productsKeys = Object.keys(byProduct);
        if (productsKeys.length === 0) return null;
        const nCos = (byProduct[productsKeys[0]] || []).length;
        const cols = [
          { key: 'product', label: 'Product' },
          ...Array.from({ length: nCos }, (_, i) => ({
            key: 'c' + i,
            label: 'Co. ' + (i + 1),
            align: 'right',
          })),
        ];
        const rows = productsKeys.map((p) => {
          const row = { product: 'Product ' + p };
          (byProduct[p] || []).forEach((s, i) => {
            row['c' + i] = typeof s === 'number' ? pct(s) : pretty(s);
          });
          return row;
        });
        return (
          <DataTable
            key={area}
            title={'Market shares — ' + (AREA_LABELS[area] || area)}
            columns={cols}
            rows={rows}
          />
        );
      })}

      <h2>Economic Information</h2>
      <KV obj={{
        'GDP growth': economic.gdp_growth_pct != null ? pct(economic.gdp_growth_pct) : '—',
        'Unemployment': economic.unemployment_pct != null ? pct(economic.unemployment_pct) : '—',
        'Central bank rate': economic.central_bank_rate != null ? pct(economic.central_bank_rate) : '—',
        'Inflation': economic.inflation_pct != null ? pct(economic.inflation_pct) : '—',
        'Recession': yesNo(economic.recession),
        'Material price next quarter': pretty(economic.material_price_next_q),
      }} />
    </div>
  );
}

export default function Reports() {
  const { auth, logout } = useAuth();
  const [qlist, setQlist] = useState([]);
  const [year, setYear] = useState('');
  const [quarter, setQuarter] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    quarters()
      .then((qs) => {
        if (cancelled) return;
        const list = (qs || []).slice().sort((a, b) => a.year - b.year || a.quarter - b.quarter);
        setQlist(list);
        const pub = list.filter((q) => q.status === 'published');
        const pick = pub.length > 0 ? pub[pub.length - 1] : list[list.length - 1];
        if (pick) {
          setYear(pick.year);
          setQuarter(pick.quarter);
        }
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load the quarter list.');
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const load = async (y, q) => {
    setLoading(true);
    setError('');
    setReport(null);
    try {
      const r = await getReport(y, q);
      setReport(r);
    } catch (e) {
      setError(
        (e.body && e.body.error) ||
          'Report not published yet. Reports appear here after the quarter is processed.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (year !== '' && quarter !== '') load(year, quarter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, quarter]);

  const years = [...new Set(qlist.map((q) => q.year))];

  return (
    <div className="topaz-page">
      <TopazHeader team={auth?.team} industry={auth?.industry} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/reports" />
      <h2>Management Reports</h2>

      <fieldset>
        <legend>Select Report</legend>
        <div className="form-row">
          <label className="field-label">Year</label>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => (
              <option key={y} value={y}>
                Year {y}
              </option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label className="field-label">Quarter</label>
          <select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
            {[1, 2, 3, 4].map((q) => (
              <option key={q} value={q}>
                Quarter {q}
              </option>
            ))}
          </select>
        </div>
        <p className="note">
          Quarter status:{' '}
          {qlist.find((q) => q.year === Number(year) && q.quarter === Number(quarter))
            ?.status || '—'}
        </p>
      </fieldset>

      {loading ? <p>Loading report…</p> : null}
      {!loading && error ? <div className="error-list">{error}</div> : null}
      {!loading && !error && report ? <Section report={report} /> : null}

      <div className="footer-note">Topaz-VBE replica — Edit 515 Virtual Business Environment</div>
    </div>
  );
}
