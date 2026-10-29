import { LEVEL_LABEL } from '../../lib/labels'
import type { LoadState } from '../../lib/useLoad'
import type { AdvisoryChanges, Asset } from '../../types/scenario'

const MAX_MOVES = 3

interface Props {
  state: LoadState<AdvisoryChanges>
  assetsById: Map<string, Asset>
  onRetry: () => void
}

export function ChangesPanel({ state, assetsById, onRetry }: Props) {
  return (
    <section className="card" aria-label="What changed">
      <h2>What changed</h2>
      {state.status === 'loading' && <p className="hint">Comparing with the previous advisory…</p>}
      {state.status === 'error' && (
        <div role="alert">
          <p className="error-text">Could not load the changes: {state.error.message}</p>
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
      {state.status === 'ok' && <ChangeList changes={state.data} assetsById={assetsById} />}
    </section>
  )
}

export function ChangeList({ changes, assetsById }: { changes: AdvisoryChanges; assetsById: Map<string, Asset> }) {
  if (changes.previous_advisory_no === null) {
    return <p className="hint">First advisory: this is the initial forecast and the initial ranking.</p>
  }
  const items: string[] = []
  if (changes.landfall_shift) {
    items.push(
      `Forecast landfall moved ${Math.round(changes.landfall_shift.distance_km)} km ${changes.landfall_shift.direction}.`,
    )
  }
  if (changes.activation_level_to && changes.activation_level_to !== changes.activation_level_from) {
    items.push(`Activation level is now ${LEVEL_LABEL[changes.activation_level_to]}.`)
  }
  for (const move of changes.rank_moves.slice(0, MAX_MOVES)) {
    const name = assetsById.get(move.asset_id)?.name ?? ''
    const verb = move.to_rank < move.from_rank ? 'rose' : 'fell'
    items.push(`${move.asset_id} ${name} ${verb} from rank ${move.from_rank} to ${move.to_rank}.`)
  }
  if (items.length === 0) {
    return <p className="hint">No change in the forecast track or the ranking.</p>
  }
  return (
    <ul className="changes">
      {items.map((text) => (
        <li key={text}>{text}</li>
      ))}
    </ul>
  )
}
