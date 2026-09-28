import React from 'react';
import DataTable from './DataTable.jsx';
import { yesNo } from '../format.js';

export const AREA_LABELS = {
  export: 'Export',
  south: 'South',
  west: 'West',
  north: 'North',
};

export const AREAS = ['export', 'south', 'west', 'north'];

export const SHIFT_LABELS = { 1: 'Single', 2: 'Double', 3: 'Treble' };

function arr(d, path, i, fb = '—') {
  const v = path.reduce((o, k) => (o == null ? o : o[k]), d);
  if (!Array.isArray(v) || v[i] === undefined || v[i] === null) return fb;
  return v[i];
}

/* Read-only summary of a decision form, grouped by section.
   Used by the Review page and the "Decisions Made" report section. */
export default function DecisionSummary({ data }) {
  if (!data) return <p className="note">No decision data.</p>;
  const d = data;

  const priceRows = [0, 1, 2].map((i) => ({
    product: 'Product ' + (i + 1),
    export_price: '£' + arr(d, ['prices', 'export'], i),
    home_price: '£' + arr(d, ['prices', 'home'], i),
    improvement: yesNo(arr(d, ['product_improvements'], i, false)),
  }));

  const promoRows = [0, 1, 2].map((i) => ({
    product: 'Product ' + (i + 1),
    trade_press: "£'" + '000 ' + arr(d, ['promotion', 'trade_press'], i),
    advertising: "£'" + '000 ' + arr(d, ['promotion', 'advertising'], i),
    support: "£'" + '000 ' + arr(d, ['promotion', 'support'], i),
    merchandising: "£'" + '000 ' + arr(d, ['promotion', 'merchandising'], i),
  }));

  const salesRows = AREAS.map((a) => ({
    area: AREA_LABELS[a],
    salespeople: (d.salespeople && d.salespeople[a]) ?? '—',
  }));

  const makeRows = AREAS.map((a) => ({
    area: AREA_LABELS[a],
    p1: arr(d, ['make_deliver', a], 0),
    p2: arr(d, ['make_deliver', a], 1),
    p3: arr(d, ['make_deliver', a], 2),
  }));

  const asmRows = [0, 1, 2].map((i) => ({
    product: 'Product ' + (i + 1),
    minutes: arr(d, ['assembly_time_minutes'], i),
  }));

  return (
    <div>
      <h3>Marketing</h3>
      <DataTable
        title="Selling prices (£ per unit)"
        columns={[
          { key: 'product', label: 'Product' },
          { key: 'export_price', label: 'Export market', align: 'right' },
          { key: 'home_price', label: 'Home markets', align: 'right' },
          { key: 'improvement', label: 'Product improvement', align: 'center' },
        ]}
        rows={priceRows}
      />
      <DataTable
        title="Promotion expenditure"
        columns={[
          { key: 'product', label: 'Product' },
          { key: 'trade_press', label: 'Trade press', align: 'right' },
          { key: 'advertising', label: 'Advertising', align: 'right' },
          { key: 'support', label: 'Support', align: 'right' },
          { key: 'merchandising', label: 'Merchandising', align: 'right' },
        ]}
        rows={promoRows}
      />
      <DataTable
        title="Salespeople by area"
        columns={[
          { key: 'area', label: 'Area' },
          { key: 'salespeople', label: 'Salespeople', align: 'right' },
        ]}
        rows={salesRows}
      />
      <table className="kv">
        <tbody>
          <tr>
            <th>Salesperson quarterly salary</th>
            <td>£'000 {d.sales_remuneration?.quarterly_salary_000 ?? '—'}</td>
          </tr>
          <tr>
            <th>Salesperson commission</th>
            <td>{d.sales_remuneration?.commission_pct ?? '—'}%</td>
          </tr>
        </tbody>
      </table>

      <h3>Production</h3>
      <DataTable
        title="Assembly time allowed"
        columns={[
          { key: 'product', label: 'Product' },
          { key: 'minutes', label: 'Minutes per unit', align: 'right' },
        ]}
        rows={asmRows}
      />
      <DataTable
        title="Make and deliver (units scheduled)"
        columns={[
          { key: 'area', label: 'Area' },
          { key: 'p1', label: 'Product 1', align: 'right' },
          { key: 'p2', label: 'Product 2', align: 'right' },
          { key: 'p3', label: 'Product 3', align: 'right' },
        ]}
        rows={makeRows}
      />
      <table className="kv">
        <tbody>
          <tr>
            <th>Shift level</th>
            <td>{SHIFT_LABELS[d.shift_level] || d.shift_level}</td>
          </tr>
          <tr>
            <th>Contract maintenance</th>
            <td>{d.contract_maintenance_hours ?? '—'} hours/machine</td>
          </tr>
          <tr>
            <th>Machines to sell</th>
            <td>{d.machines_to_sell ?? '—'}</td>
          </tr>
          <tr>
            <th>New machines to order</th>
            <td>{d.new_machines_to_order ?? '—'}</td>
          </tr>
          <tr>
            <th>Raw material order</th>
            <td>
              {d.raw_material?.units_to_order ?? '—'} units · Supplier{' '}
              {d.raw_material?.supplier_no ?? '—'} · {d.raw_material?.num_deliveries ?? '—'}{' '}
              deliveries
            </td>
          </tr>
          <tr>
            <th>Vehicles to buy / sell</th>
            <td>
              {d.vans_to_buy ?? 0} / {d.vans_to_sell ?? 0}
            </td>
          </tr>
        </tbody>
      </table>

      <h3>Personnel</h3>
      <table className="kv">
        <tbody>
          <tr>
            <th>Salespeople: recruit / dismiss / train</th>
            <td>
              {d.salespeople_changes?.recruit ?? 0} / {d.salespeople_changes?.dismiss ?? 0} /{' '}
              {d.salespeople_changes?.train ?? 0}
            </td>
          </tr>
          <tr>
            <th>Assembly workers: recruit / dismiss / train</th>
            <td>
              {d.assembly_changes?.recruit ?? 0} / {d.assembly_changes?.dismiss ?? 0} /{' '}
              {d.assembly_changes?.train ?? 0}
            </td>
          </tr>
          <tr>
            <th>Assembly wage rate</th>
            <td>
              £{d.assembly_wage?.pounds ?? '—'}.{String(d.assembly_wage?.pence ?? '00').padStart(2, '0')}{' '}
              per hour
            </td>
          </tr>
        </tbody>
      </table>

      <h3>Finance</h3>
      <table className="kv">
        <tbody>
          <tr>
            <th>Dividend rate</th>
            <td>{d.dividend_rate_pence ?? '—'} pence per share</td>
          </tr>
          <tr>
            <th>Days credit allowed to customers</th>
            <td>{d.days_credit_allowed ?? '—'} days</td>
          </tr>
          <tr>
            <th>Information wanted: other companies</th>
            <td>{yesNo(d.info_wanted?.other_companies)} (£5,000 charge)</td>
          </tr>
          <tr>
            <th>Information wanted: market shares</th>
            <td>{yesNo(d.info_wanted?.market_shares)} (£5,000 charge)</td>
          </tr>
          <tr>
            <th>Management budget</th>
            <td>£'000 {d.management_budget_000 ?? '—'}</td>
          </tr>
          <tr>
            <th>Research expenditure</th>
            <td>£'000 {d.research_expenditure_000 ?? '—'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
