import { useMemo, useState } from 'react'
import type { ApiError } from '../../api/client'
import { getClauses, streamChat } from '../../api/scenario'
import { toApiError, useLoad } from '../../lib/useLoad'
import type { ChatReply, ChatTurn, CopilotStep } from '../../types/scenario'
import { HowIGotThis } from './HowIGotThis'
import { stepLabel } from './steps'

const SUGGESTIONS = [
  'Why is PS-14 ranked where it is?',
  'What are the top risks?',
  'What depends on SUB-07?',
  'What does P-4.7 say?',
]

interface Exchange {
  question: string
  reply: ChatReply
  steps: CopilotStep[]
}

const loadClauses = () => getClauses()

export function CopilotPanel({ onSelectAsset }: { onSelectAsset: (assetId: string) => void }) {
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [live, setLive] = useState<CopilotStep[]>([])
  const [error, setError] = useState<ApiError | null>(null)
  const [openClause, setOpenClause] = useState<string | null>(null)
  const [lastQuestion, setLastQuestion] = useState('')
  const { state: clausesState, retry: retryClauses } = useLoad(loadClauses)
  const clauses = useMemo(
    () => new Map(clausesState.status === 'ok' ? clausesState.data.map((c) => [c.id, c]) : []),
    [clausesState],
  )

  async function ask(question: string) {
    const text = question.trim()
    if (!text || busy) return
    const history: ChatTurn[] = exchanges.flatMap((e) => [
      { role: 'user', content: e.question },
      { role: 'assistant', content: e.reply.answer },
    ])
    setBusy(true)
    setError(null)
    setLastQuestion(text)
    setLive([])
    const steps: CopilotStep[] = []
    try {
      // the steps show while the turn runs; the answer only once it has passed validation
      const reply = await streamChat(text, history, (step) => {
        steps.push(step)
        setLive([...steps])
      })
      setExchanges((previous) => [...previous, { question: text, reply, steps }])
      setDraft('')
    } catch (e) {
      setError(toApiError(e))
    } finally {
      setBusy(false)
      setLive([])
    }
  }

  const shown = openClause ? clauses.get(openClause) : undefined

  return (
    <section className="copilot">
      <p className="hint small">
        Answers come from the same data as the screens, about the current advisory; every ID and number in an answer was
        returned by a tool.
      </p>
      {exchanges.length === 0 && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="secondary" onClick={() => ask(s)} disabled={busy}>
              {s}
            </button>
          ))}
        </div>
      )}
      <ol className="chat" aria-live="polite">
        {exchanges.map((e, i) => (
          <li key={i}>
            <p className="chat-question">{e.question}</p>
            <div className="chat-answer">
              <p>{e.reply.answer}</p>
              <p className="chips">
                {e.reply.citations.map((c) =>
                  c.kind === 'asset' ? (
                    <button key={c.id} type="button" className="chip chip-button" onClick={() => onSelectAsset(c.id)}>
                      {c.id}
                    </button>
                  ) : (
                    <button
                      key={c.id}
                      type="button"
                      className="chip chip-clause"
                      aria-expanded={openClause === c.id}
                      onClick={() => setOpenClause(openClause === c.id ? null : c.id)}
                    >
                      {c.id}
                    </button>
                  ),
                )}
              </p>
              <p className="hint small">
                {e.reply.fallback ? 'Offline answer (the AI answer was not used)' : e.reply.provider === 'template' ? 'Offline answer' : 'AI answer'}
                {e.reply.advisory !== null && ` · advisory ${e.reply.advisory}`}
                {e.reply.tools_used.length > 0 && ` · tools: ${e.reply.tools_used.join(', ')}`}
              </p>
              <HowIGotThis work={e.reply.work} steps={e.steps} />
            </div>
          </li>
        ))}
      </ol>
      {shown && (
        <aside className="clause-text" aria-label={`Clause ${shown.id}`}>
          <strong>
            {shown.id} {shown.title}.
          </strong>{' '}
          {shown.text}
        </aside>
      )}
      {busy && (
        <div className="copilot-progress" role="status" aria-label="Copilot progress">
          <p className="hint">Working on it…</p>
          <ol className="work-list">
            {live.map((step, i) => (
              <li key={i}>{stepLabel(step)}</li>
            ))}
          </ol>
        </div>
      )}
      {error && (
        <p role="alert" className="error-text small">
          Could not answer: {error.message}{' '}
          <button type="button" className="link" onClick={() => ask(lastQuestion)}>
            Retry
          </button>
        </p>
      )}
      {clausesState.status === 'error' && (
        <p role="alert" className="error-text small">
          Clause texts unavailable: {clausesState.error.message}{' '}
          <button type="button" className="link" onClick={retryClauses}>
            Retry
          </button>
        </p>
      )}
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault()
          void ask(draft)
        }}
      >
        <label className="reason">
          Ask the copilot
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Why is SUB-07 ranked where it is?" />
        </label>
        <button type="submit" disabled={busy || !draft.trim()}>
          Ask
        </button>
      </form>
    </section>
  )
}
