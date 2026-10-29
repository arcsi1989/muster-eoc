import type { ApiError } from '../../api/client'
import { roleLabel } from '../../lib/roles'
import type { ActivationLevel, Asset, Clause, DecisionAction, DecisionPackage, PackageItem, Role } from '../../types/scenario'
import { ChangeList } from '../scenario/ChangesPanel'
import { ActivationProposalCard } from './ActivationProposalCard'
import { ItemCard } from './ItemCard'
import { SitrepSection } from './SitrepSection'

interface Props {
  pkg: DecisionPackage
  assetsById: Map<string, Asset>
  /** a refused or failed decision, shown on its item */
  error: { itemId: number; error: ApiError } | null
  busy: boolean
  onDecide: (item: PackageItem, action: DecisionAction, reason?: string) => void
  role: Role
  /** of the package's advisory; null while unknown */
  hoursToLandfall: number | null
  declareError: ApiError | null
  onDeclare: (level: ActivationLevel, reason?: string) => void
  /** the situation report can be approved while its advisory is current */
  sitrepOpen: boolean
  clauses: Map<string, Clause>
  sitrepError: ApiError | null
  onApproveSitrep: (text: string) => void
  onSelectAsset: (assetId: string) => void
}

const COLLAPSE_ABOVE = 3

function groupByRule(items: PackageItem[]) {
  const groups = new Map<string, PackageItem[]>()
  for (const item of items) groups.set(item.rule_id, [...(groups.get(item.rule_id) ?? []), item])
  return [...groups.entries()]
}

export function PackageView({
  pkg,
  assetsById,
  error,
  busy,
  onDecide,
  role,
  hoursToLandfall,
  declareError,
  onDeclare,
  sitrepOpen,
  clauses,
  sitrepError,
  onApproveSitrep,
  onSelectAsset,
}: Props) {
  const open = pkg.status === 'open'
  const conflicts = pkg.items.filter((i) => i.kind === 'conflict')
  const gaps = pkg.items.filter((i) => i.kind === 'gap')
  const proposal = pkg.items.find((i) => i.kind === 'proposal')
  const pending = pkg.items.filter((i) => i.status === 'pending').length
  const errorFor = (item: PackageItem) => (error?.itemId === item.id ? error.error : null)

  const groups = (items: PackageItem[]) =>
    groupByRule(items).map(([ruleId, group]) => (
      <details key={ruleId} open={group.length <= COLLAPSE_ABOVE}>
        <summary>
          <span className="chip">{ruleId}</span> {group[0].title} · {group.length}
        </summary>
        <ul>
          {group.map((item) => (
            <ItemCard key={item.id} item={item} open={open} busy={busy} onDecide={onDecide} error={errorFor(item)} />
          ))}
        </ul>
      </details>
    ))

  return (
    <div className="findings">
      {proposal && pkg.proposed_activation_level && (
        <ActivationProposalCard
          item={proposal}
          proposed={pkg.proposed_activation_level}
          declared={pkg.activation_level}
          hoursToLandfall={hoursToLandfall}
          role={role}
          open={open}
          busy={busy}
          error={declareError}
          onDeclare={onDeclare}
        />
      )}
      <p className="hint small">
        {open
          ? `${pending} of ${pkg.items.length} items await a decision. The ${roleLabel(pkg.decides_as_commander)} holds overrides at this activation level. In this prototype an approval records the action as done.`
          : 'This decision package is closed; undecided items were closed as not decided.'}
      </p>
      <section aria-label="What changed">
        <h3>What changed</h3>
        <ChangeList changes={pkg.changes} assetsById={assetsById} />
      </section>
      {conflicts.length > 0 && (
        <section aria-label="Conflicts">
          <h3>Conflicts (Incident Commander decides) · {conflicts.length}</h3>
          {groups(conflicts)}
        </section>
      )}
      <section aria-label="Gaps">
        <h3>Gaps and proposed actions · {gaps.length}</h3>
        {gaps.length === 0 && <p className="hint">No open gaps.</p>}
        {groups(gaps)}
      </section>
      {pkg.draft && pkg.draft_text !== null && (
        <SitrepSection
          key={pkg.advisory_no}
          draft={pkg.draft}
          draftText={pkg.draft_text}
          sitrep={pkg.sitrep}
          open={sitrepOpen}
          clauses={clauses}
          error={sitrepError}
          busy={busy}
          onApprove={onApproveSitrep}
          onSelectAsset={onSelectAsset}
        />
      )}
    </div>
  )
}
