import { useState, useEffect } from 'react';
import { quarters, getReport } from './api.js';

/* Returns the most recent PUBLISHED quarter's report (or null).
   Used by decision pages to show the current position (staff, cash...). */
export function useLastPublishedReport() {
  const [state, setState] = useState({ loading: true, report: null, quarter: null, error: null });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const qs = await quarters();
        const published = (qs || [])
          .filter((q) => q.status === 'published')
          .sort((a, b) => a.year - b.year || a.quarter - b.quarter);
        if (published.length === 0) {
          if (!cancelled) setState({ loading: false, report: null, quarter: null, error: null });
          return;
        }
        const last = published[published.length - 1];
        const report = await getReport(last.year, last.quarter);
        if (!cancelled) setState({ loading: false, report, quarter: last, error: null });
      } catch (e) {
        if (!cancelled)
          setState({
            loading: false,
            report: null,
            quarter: null,
            error: 'Could not load the last published report.',
          });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

/* Own company's row from the group/competitor section of a report. */
export function ownCompany(report) {
  const companies = (report && report.group && report.group.companies) || [];
  const meta = (report && report.meta) || {};
  return (
    companies.find((c) => c.company_number === meta.company_number) || companies[0] || null
  );
}
