import { riskColor } from '../../lib/riskColor'
import type { Asset, RiskItem } from '../../types/scenario'

interface Props {
  items: RiskItem[]
  assetsById: Map<string, Asset>
}

function RankChange({ item }: { item: RiskItem }) {
  if (item.previous_rank === null) return <span className="move move-none">new</span>
  const delta = item.previous_rank - item.rank
  if (delta === 0) return <span className="move move-none" aria-label="unchanged">–</span>
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

export function RiskList({ items, assetsById }: Props) {
  if (items.length === 0) {
    return <p className="hint">No assets were scored for this advisory.</p>
  }
  return (
    <ol className="risk-list">
      {items.map((item) => {
        const asset = assetsById.get(item.asset_id)
        return (
          <li key={item.asset_id}>
            <span className="rank">{item.rank}</span>
            <span className="swatch" style={{ background: riskColor(item.score) }} aria-hidden />
            <span className="asset">
              <strong>{item.asset_id}</strong> {asset?.name}
            </span>
            <span className="score">{item.score.toFixed(2)}</span>
            <RankChange item={item} />
          </li>
        )
      })}
    </ol>
  )
}
