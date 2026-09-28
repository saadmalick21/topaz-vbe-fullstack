import React, { useEffect } from 'react';
import { useAuth } from '../AuthContext.jsx';
import { useDecisions } from '../DecisionContext.jsx';
import TopazHeader from '../components/TopazHeader.jsx';
import ClassicNav from '../components/ClassicNav.jsx';
import ActionButtons from '../components/ActionButtons.jsx';
import { NumField, SelectField, CellInput } from '../components/Fields.jsx';
import { TEAM_LINKS } from './Main.jsx';
import { AREAS, AREA_LABELS, SHIFT_LABELS } from '../components/DecisionSummary.jsx';

export default function Production() {
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

  const setIdx = (path, i, v) => {
    const cur = path.reduce((o, k) => (o == null ? o : o[k]), data) || [];
    const next = cur.slice();
    next[i] = v;
    set(path, next);
  };

  return (
    <div className="topaz-page">
      <TopazHeader team={auth?.team} industry={auth?.industry} quarter={year ? { year, quarter, status: submitted ? 'submitted' : 'open' } : null} onLogout={logout} />
      <ClassicNav links={TEAM_LINKS} current="/production" />
      <h2>Production Decisions</h2>
      {submitted ? (
        <div className="info-box">
          Decisions for this quarter have been submitted — the form is locked until the
          quarter is processed.
        </div>
      ) : null}

      <fieldset>
        <legend>Assembly Time Allowed</legend>
        {[0, 1, 2].map((i) => (
          <NumField
            key={i}
            label={'Product ' + (i + 1) + ' assembly time'}
            suffix="minutes per unit"
            value={data.assembly_time_minutes?.[i]}
            onChange={(v) => setIdx(['assembly_time_minutes'], i, v)}
            min={0}
            integers
            disabled={dis}
          />
        ))}
        <p className="note">
          Minimum assembly minutes: Product 1 — 100, Product 2 — 150, Product 3 — 300.
        </p>
      </fieldset>

      <fieldset>
        <legend>Make and Deliver (units scheduled per area and product)</legend>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Area</th>
                <th className="num">Product 1</th>
                <th className="num">Product 2</th>
                <th className="num">Product 3</th>
              </tr>
            </thead>
            <tbody>
              {AREAS.map((a) => (
                <tr key={a}>
                  <td>{AREA_LABELS[a]}</td>
                  {[0, 1, 2].map((i) => (
                    <td className="num" key={i}>
                      <CellInput
                        value={data.make_deliver?.[a]?.[i]}
                        onChange={(v) => setIdx(['make_deliver', a], i, v)}
                        disabled={dis}
                        integers
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </fieldset>

      <fieldset>
        <legend>Shift Working</legend>
        <SelectField
          label="Shift level"
          value={data.shift_level}
          onChange={(v) => set(['shift_level'], v)}
          disabled={dis}
          options={[
            { value: 1, label: '1 — Single shift' },
            { value: 2, label: '2 — Double shift' },
            { value: 3, label: '3 — Treble shift' },
          ]}
        />
        <p className="note">
          Single: 576 machine hours/quarter · Double: 1068 · Treble: 1602.
        </p>
      </fieldset>

      <fieldset>
        <legend>Machines and Maintenance</legend>
        <NumField
          label="Contract maintenance"
          suffix="hours per machine"
          value={data.contract_maintenance_hours}
          onChange={(v) => set(['contract_maintenance_hours'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="Machines to sell"
          value={data.machines_to_sell}
          onChange={(v) => set(['machines_to_sell'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="New machines to order"
          value={data.new_machines_to_order}
          onChange={(v) => set(['new_machines_to_order'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <p className="note">
          A machine costs £200,000 (£100,000 payable at order, £100,000 on installation).
        </p>
      </fieldset>

      <fieldset>
        <legend>Raw Material Order</legend>
        <NumField
          label="Units to order"
          value={data.raw_material?.units_to_order}
          onChange={(v) => set(['raw_material', 'units_to_order'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <SelectField
          label="Supplier"
          value={data.raw_material?.supplier_no}
          onChange={(v) => set(['raw_material', 'supplier_no'], v)}
          disabled={dis}
          options={[
            { value: 0, label: 'Supplier 0 — list price, no order charge' },
            { value: 1, label: 'Supplier 1 — 10% discount, £200 per order' },
            { value: 2, label: 'Supplier 2 — 15% discount, £300 per order' },
            { value: 3, label: 'Supplier 3 — 30% discount, £100 per order, automatic weekly deliveries' },
          ]}
        />
        <NumField
          label="Number of deliveries"
          value={data.raw_material?.num_deliveries}
          onChange={(v) => set(['raw_material', 'num_deliveries'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <p className="note">
          Supplier 3 makes 12 automatic weekly deliveries — set deliveries to 0 for
          Supplier 3.
        </p>
      </fieldset>

      <fieldset>
        <legend>Vehicles</legend>
        <NumField
          label="Vehicles to buy"
          value={data.vans_to_buy}
          onChange={(v) => set(['vans_to_buy'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <NumField
          label="Vehicles to sell"
          value={data.vans_to_sell}
          onChange={(v) => set(['vans_to_sell'], v)}
          min={0}
          integers
          disabled={dis}
        />
        <p className="note">A vehicle costs £15,000. Capacity: 40 / 40 / 20 units.</p>
      </fieldset>

      <ActionButtons />
      <div className="footer-note">Topaz-VBE replica — Edit 515 Virtual Business Environment</div>
    </div>
  );
}
