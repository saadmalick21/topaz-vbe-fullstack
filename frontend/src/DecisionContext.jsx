import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import {
  getDecisions,
  saveDecisions,
  resetDecisions,
  submitDecisions,
} from './api.js';

/* Default decision form values (SPEC §2). Used when the server has no
   draft yet, and as the target of "Reset to defaults". */
export const DEFAULT_DECISIONS = {
  product_improvements: [false, false, false],
  prices: {
    export: [120.0, 180.0, 260.0],
    home: [110.0, 165.0, 240.0],
  },
  promotion: {
    trade_press: [8.0, 6.0, 4.0],
    advertising: [20.0, 15.0, 10.0],
    support: [5.0, 4.0, 3.0],
    merchandising: [6.0, 5.0, 4.0],
  },
  assembly_time_minutes: [110, 160, 320],
  salespeople: { export: 2, south: 4, west: 3, north: 5 },
  sales_remuneration: { quarterly_salary_000: 3.0, commission_pct: 5.0 },
  assembly_wage: { pounds: 9, pence: 50 },
  shift_level: 1,
  management_budget_000: 45.0,
  contract_maintenance_hours: 40,
  machines_to_sell: 0,
  dividend_rate_pence: 4.0,
  days_credit_allowed: 30,
  vans_to_buy: 0,
  vans_to_sell: 0,
  info_wanted: { other_companies: false, market_shares: false },
  make_deliver: {
    export: [800, 500, 300],
    south: [600, 400, 200],
    west: [400, 300, 150],
    north: [900, 600, 350],
  },
  research_expenditure_000: 12.0,
  salespeople_changes: { recruit: 0, dismiss: 0, train: 2 },
  assembly_changes: { recruit: 2, dismiss: 0, train: 4 },
  raw_material: { units_to_order: 4000, supplier_no: 1, num_deliveries: 2 },
  new_machines_to_order: 0,
};

const MIRROR_KEY = 'topaz_decisions_mirror';

function mirrorToLocalStorage(year, quarter, data) {
  try {
    localStorage.setItem(
      MIRROR_KEY,
      JSON.stringify({ year, quarter, data, savedAt: new Date().toISOString() })
    );
  } catch (e) {
    /* storage full / unavailable — server remains source of truth */
  }
}

function readMirror() {
  try {
    const raw = localStorage.getItem(MIRROR_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function getPath(obj, path) {
  return path.reduce((o, k) => (o == null ? o : o[k]), obj);
}

function setPath(obj, path, value) {
  const copy = structuredClone(obj);
  let cur = copy;
  for (let i = 0; i < path.length - 1; i++) {
    cur = cur[path[i]];
  }
  cur[path[path.length - 1]] = value;
  return copy;
}

const DecisionContext = createContext(null);

export function useDecisions() {
  return useContext(DecisionContext);
}

export function DecisionProvider({ children }) {
  const [state, setState] = useState({
    loading: true,
    saving: false,
    data: null,
    year: null,
    quarter: null,
    submitted: false,
    submittedAt: null,
    autoPass: false,
    errors: [],
    warnings: [],
    confirmation: null,
    savedAt: null,
    fromMirror: false,
  });

  const refresh = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, errors: [] }));
    try {
      const res = await getDecisions();
      const data = res.data
        ? res.data
        : structuredClone(DEFAULT_DECISIONS);
      mirrorToLocalStorage(res.year, res.quarter, data);
      setState((s) => ({
        ...s,
        loading: false,
        data,
        year: res.year,
        quarter: res.quarter,
        submitted: !!res.submitted,
        submittedAt: res.submitted_at || null,
        autoPass: !!res.auto_pass,
        fromMirror: false,
      }));
    } catch (e) {
      // Server unreachable: fall back to the local mirror if one exists.
      const m = readMirror();
      if (m && m.data) {
        setState((s) => ({
          ...s,
          loading: false,
          data: m.data,
          year: m.year,
          quarter: m.quarter,
          fromMirror: true,
          errors: ['Could not reach the server — showing your last saved draft.'],
        }));
      } else {
        setState((s) => ({
          ...s,
          loading: false,
          errors: [
            'Could not load the decision form from the server. Please check your connection and try again.',
          ],
        }));
      }
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const set = useCallback((path, value) => {
    setState((s) => ({
      ...s,
      data: s.data ? setPath(s.data, path, value) : s.data,
      errors: [],
      confirmation: null,
    }));
  }, []);

  const update = useCallback((fn) => {
    setState((s) => ({
      ...s,
      data: s.data ? fn(structuredClone(s.data)) : s.data,
      errors: [],
      confirmation: null,
    }));
  }, []);

  const save = useCallback(async () => {
    let ok = false;
    setState((s) => ({ ...s, saving: true, errors: [], warnings: [] }));
    try {
      const res = await saveDecisions(state.data);
      setState((s) => {
        mirrorToLocalStorage(s.year, s.quarter, s.data);
        return {
          ...s,
          saving: false,
          warnings: res.warnings || [],
          savedAt: new Date().toISOString(),
        };
      });
      ok = true;
    } catch (e) {
      const errs =
        (e.body && (e.body.errors || (e.body.error ? [e.body.error] : null))) ||
        ['Save failed — please try again.'];
      setState((s) => ({ ...s, saving: false, errors: errs }));
    }
    return ok;
  }, [state.data]);

  const reset = useCallback(async () => {
    setState((s) => ({ ...s, saving: true, errors: [], warnings: [] }));
    try {
      const res = await resetDecisions();
      const data = res.data || structuredClone(DEFAULT_DECISIONS);
      setState((s) => {
        mirrorToLocalStorage(s.year, s.quarter, data);
        return {
          ...s,
          saving: false,
          data,
          warnings: [],
          confirmation: null,
          savedAt: new Date().toISOString(),
        };
      });
      return true;
    } catch (e) {
      const errs =
        (e.body && (e.body.errors || (e.body.error ? [e.body.error] : null))) ||
        ['Reset failed — please try again.'];
      setState((s) => ({ ...s, saving: false, errors: errs }));
      return false;
    }
  }, []);

  const submit = useCallback(async () => {
    setState((s) => ({ ...s, saving: true, errors: [], warnings: [] }));
    try {
      const res = await submitDecisions();
      setState((s) => ({
        ...s,
        saving: false,
        submitted: true,
        confirmation: res.confirmation || 'Decisions submitted.',
      }));
      return true;
    } catch (e) {
      const errs =
        (e.body && (e.body.errors || (e.body.error ? [e.body.error] : null))) ||
        ['Submit failed — please try again.'];
      setState((s) => ({ ...s, saving: false, errors: errs }));
      return false;
    }
  }, []);

  const value = {
    ...state,
    set,
    update,
    get: (path) => getPath(state.data, path),
    refresh,
    save,
    reset,
    submit,
  };

  return <DecisionContext.Provider value={value}>{children}</DecisionContext.Provider>;
}
