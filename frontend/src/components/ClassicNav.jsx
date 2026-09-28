import React from 'react';

/* Horizontal navigation as a bordered table row of links (old-school). */
export default function ClassicNav({ links, current }) {
  return (
    <table className="classic-nav">
      <tbody>
        <tr>
          {links.map((l) => (
            <td key={l.to} className={l.to === current ? 'current' : ''}>
              <a href={'#' + l.to}>{l.label}</a>
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );
}
