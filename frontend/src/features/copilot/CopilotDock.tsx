import { CopilotPanel } from './CopilotPanel'

interface Props {
  open: boolean
  onClose: () => void
  onSelectAsset: (assetId: string) => void
}

/** The copilot beside every page. It stays mounted while closed, so the conversation survives
 * closing it and changing pages; every question is answered about the current advisory. */
export function CopilotDock({ open, onClose, onSelectAsset }: Props) {
  return (
    <aside id="copilot-dock" className="drawer copilot-dock" aria-label="Copilot" hidden={!open}>
      <div className="drawer-head">
        <h2>Copilot</h2>
        <button type="button" className="secondary" onClick={onClose}>
          Close
        </button>
      </div>
      <CopilotPanel onSelectAsset={onSelectAsset} />
    </aside>
  )
}
