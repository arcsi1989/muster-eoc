import { formatIssuedAt } from '../../lib/labels'
import type { LineageEntry } from '../../types/scenario'

export function DataQualityTable({ entries }: { entries: LineageEntry[] }) {
  if (entries.length === 0) return <p className="hint">No files were loaded.</p>
  return (
    <table className="lineage">
      <caption className="visually-hidden">Loaded gold files</caption>
      <thead>
        <tr>
          <th scope="col">File</th>
          <th scope="col">Rows accepted</th>
          <th scope="col">Rows rejected</th>
          <th scope="col">SHA-256</th>
          <th scope="col">Loaded</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.file} className={entry.rows_rejected > 0 ? 'has-issues' : undefined}>
            <td>
              <code>{entry.file}</code>
              {entry.issues.length > 0 && (
                <ul className="issues">
                  {entry.issues.map((issue) => (
                    <li key={issue.row}>
                      Row {issue.row}
                      {issue.record_id && ` (${issue.record_id})`}: {issue.reason}
                    </li>
                  ))}
                </ul>
              )}
            </td>
            <td className="num">{entry.rows_ok}</td>
            <td className="num">{entry.rows_rejected}</td>
            <td>
              <code title={entry.sha256}>{entry.sha256.slice(0, 12)}…</code>
            </td>
            <td>{formatIssuedAt(entry.loaded_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
