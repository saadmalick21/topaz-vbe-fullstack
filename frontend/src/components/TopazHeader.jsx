import React from 'react';

export default function TopazHeader({ team, industry, quarter, admin, onLogout }) {
  return (
    <div className="header-bar">
      <table>
        <tbody>
          <tr>
            <td>
              <h1>Topaz-Vbe — Virtual Business Environment</h1>
              <div className="small">Decision entry and management reporting system</div>
            </td>
            <td className="header-right">
              {admin && (
                <>
                  Logged in as: <b>Administrator</b>
                  <br />
                  <button onClick={onLogout}>Log out</button>
                </>
              )}
              {team && (
                <>
                  Company: <b>{team.name || 'Company ' + team.company_number}</b>
                  <br />
                  Group Number <b>{team.group_number}</b> · Company Number{' '}
                  <b>{team.company_number}</b>
                  <br />
                  Industry: <b>{industry ? industry.name : '—'}</b>
                  {industry && industry.simulation_code
                    ? ' [' + industry.simulation_code + ']'
                    : ''}
                  <br />
                  {quarter && (
                    <>
                      Year <b>{quarter.year}</b>, Quarter <b>{quarter.quarter}</b> —{' '}
                      <b>{quarter.status}</b>
                    </>
                  )}
                  <br />
                  <button onClick={onLogout}>Log out</button>
                </>
              )}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
