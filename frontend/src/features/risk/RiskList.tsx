import { formatCustomers, formatPercent } from '../../lib/format'
import { useFlip } from '../../lib/useFlip'
import { pFailColor } from '../../lib/pFailColor'
import type { Asset, RiskItem } from '../../types/scenario'

interface Props {
  items: RiskItem[]
  assetsById: Map<string, Asset>
  onSelect: (assetId: string) => void
}

function RankChange({ item }: { item: RiskItem }) {
  if (item.previous_rank === null)
    return (
      <span className="move move-none" aria-label="initial ranking">
        ·
      </span>
    )
  const delta = item.previous_rank - item.rank
  if (delta === 0)
    return (
      <span className="move move-none" aria-label="unchanged">
        –
      </span>
    )
  return delta > 0 ? (
    <span className="move move-up" aria-label={`up ${delta} from ${item.previous_rank}`}>
      ▲{delta}
    </span>
  ) : (
    <span className="move move-down" aria-label={`down ${-delta} from ${item.previous_rank}`}>
      ▼{-delta}
    </span>
  )
}

export function RiskList({ items, assetsById, onSelect }: Props) {
  // A new advisory reorders the rows in place: each row moves from its old rank to its new one.
  const flip = useFlip(items.map((i) => i.asset_id))
  if (items.length === 0) {
    return <p className="hint">No assets were scored for this advisory.</p>
  }
  return (
    <>
      <p className="hint small">
        Risk = failure probability × consequence (customer-equivalents).
        {items.every((i) => i.previous_rank === null) && ' Initial ranking: the first advisory.'}
      </p>
      <ol className="risk-list">
        {items.map((item) => {
          const asset = assetsById.get(item.asset_id)
          return (
            <li key={item.asset_id} ref={flip(item.asset_id)}>
              <button type="button" className="risk-row" onClick={() => onSelect(item.asset_id)}>
                <span className="rank">{item.rank}</span>
                <span className="swatch" style={{ background: pFailColor(item.p_fail) }} aria-hidden />
                <span className="asset">
                  <strong>{item.asset_id}</strong> {asset?.name}
                  {item.confidence !== 'high' && (
                    <span className={`confidence confidence-${item.confidence}`}> {item.confidence} confidence</span>
                  )}
                </span>
                <span className="score" title={`p_fail ${formatPercent(item.p_fail)} × ${formatCustomers(item.consequence)}`}>
                  {formatCustomers(item.risk)}
                </span>
                <RankChange item={item} />
              </button>
            </li>
          )
        })}
      </ol>
    </>
  )
}
