/* Small display formatters (pounds, counts, percents). */

export function gbp(n, dp = 0) {
  const v = Number(n);
  if (isNaN(v)) return '—';
  return (
    '£' +
    v.toLocaleString('en-GB', {
      minimumFractionDigits: dp,
      maximumFractionDigits: dp,
    })
  );
}

export function gbp2(n) {
  return gbp(n, 2);
}

export function num(n) {
  const v = Number(n);
  if (isNaN(v)) return '—';
  return v.toLocaleString('en-GB');
}

export function pct(n, dp = 1) {
  const v = Number(n);
  if (isNaN(v)) return '—';
  return v.toFixed(dp) + '%';
}

export function yesNo(b) {
  return b ? 'Yes' : 'No';
}

export function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB');
  } catch (e) {
    return String(iso);
  }
}

export function pretty(v) {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'boolean') return yesNo(v);
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}
