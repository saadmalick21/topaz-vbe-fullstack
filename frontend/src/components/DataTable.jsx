import React from 'react';

/* Compact bordered table from columns + rows. Scrolls horizontally
   inside .table-scroll on small screens. */
export default function DataTable({ title, columns, rows, footer }) {
  return (
    <div className="table-scroll">
      {title ? <h3>{title}</h3> : null}
      <table className="data">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={c.align === 'right' ? 'num' : c.align === 'center' ? 'center' : ''}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(rows || []).map((r, i) => (
            <tr key={i} className={r._rowClass || ''}>
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={c.align === 'right' ? 'num' : c.align === 'center' ? 'center' : ''}
                >
                  {r[c.key] === undefined || r[c.key] === null ? '—' : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {footer ? (
          <tfoot>
            <tr className="total">
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={c.align === 'right' ? 'num' : c.align === 'center' ? 'center' : ''}
                >
                  {footer[c.key] === undefined || footer[c.key] === null
                    ? ''
                    : footer[c.key]}
                </td>
              ))}
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}
