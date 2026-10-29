import { useState } from 'react'
import type { ApiError } from '../../api/client'
import { roleLabel } from '../../lib/roles'
import type { Clause, Draft, Sitrep } from '../../types/scenario'

interface Props {
  draft: Draft
  draftText: string
  sitrep: Sitrep | null
  open: boolean
  clauses: Map<string, Clause>
  error: ApiError | null
  busy: boolean
  onApprove: (text: string) => void
  onSelectAsset: (assetId: string) => void
}

function providerLabel(draft: Draft): string {
  if (draft.fallback) return 'Template draft (the AI draft was not used)'
  if (draft.provider === 'template') return 'Template draft (offline)'
  return `AI draft (${draft.model ?? draft.provider})`
}

/** The DRAFT situation report with citation chips, and the commander's edit-and-approve. */
export function SitrepSection({ draft, draftText, sitrep, open, clauses, error, busy, onApprove, onSelectAsset }: Props) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(draftText)
  const [openClause, setOpenClause] = useState<string | null>(null)
  const shownClause = openClause ? clauses.get(openClause) : undefined

  if (sitrep) {
    return (
      <section aria-label="Situation report" className="draft">
        <h3>
          Situation report <span className="badge status-approved">Approved</span>
        </h3>
        <p className="hint small">
          Approved by {roleLabel(sitrep.approved_by)}
          {sitrep.edited ? ', edited from the draft' : ', as drafted'}.
        </p>
        <pre className="sitrep-text">{sitrep.approved_text}</pre>
      </section>
    )
  }

  return (
    <section aria-label="Draft situation report" className="draft">
      <h3>
        Situation report <span className="badge draft-badge">{draft.status}</span>
      </h3>
      <p className="hint small">
        {providerLabel(draft)}
        {draft.prompt_version && ` · prompt ${draft.prompt_version}`}
        {draft.fallback_reason && ` · ${draft.fallback_reason}`}
      </p>
      {!editing &&
        draft.sections.map((section) => (
          <div key={section.heading}>
            <h4>{section.heading}</h4>
            {section.paragraphs.map((p, i) => (
              <p key={i} className="small">
                {p.text}{' '}
                {p.clause_ids.map((id) => (
                  <button
                    key={id}
                    type="button"
                    className="chip chip-clause"
                    title={clauses.get(id)?.title}
                    aria-expanded={openClause === id}
                    onClick={() => setOpenClause(openClause === id ? null : id)}
                  >
                    {id}
                  </button>
                ))}{' '}
                {p.asset_ids.map((id) =>
                  id.startsWith('STG-') ? (
                    <span key={id} className="chip">
                      {id}
                    </span>
                  ) : (
                    <button key={id} type="button" className="chip chip-button" onClick={() => onSelectAsset(id)}>
                      {id}
                    </button>
                  ),
                )}
              </p>
            ))}
          </div>
        ))}
      {shownClause && (
        <aside className="clause-text" aria-label={`Clause ${shownClause.id}`}>
          <strong>
            {shownClause.id} {shownClause.title}.
          </strong>{' '}
          {shownClause.text}
        </aside>
      )}
      {editing && (
        <label className="reason">
          Situation report text
          <textarea rows={12} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
      )}
      {error && (
        <p role="alert" className="error-text small">
          {error.message}
        </p>
      )}
      {open && (
        <div className="item-actions">
          {!editing && (
            <button type="button" className="secondary" onClick={() => setEditing(true)}>
              Edit
            </button>
          )}
          <button type="button" disabled={busy || !text.trim()} onClick={() => onApprove(editing ? text : draftText)}>
            Approve situation report
          </button>
        </div>
      )}
    </section>
  )
}
