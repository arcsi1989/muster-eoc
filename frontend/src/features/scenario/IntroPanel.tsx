export function IntroPanel({ total }: { total: number }) {
  return (
    <div className="intro">
      <h2>How this replay works</h2>
      <p>
        A fictional hurricane is 72 hours from landfall on Bayport County. Forecasters issue a new advisory every
        12 hours: an updated track, peak wind and storm surge.
      </p>
      <ol>
        <li>
          <strong>Issue the next advisory</strong> to receive the next of {total} forecasts.
        </li>
        <li>The app recomputes which assets are most at risk and shows what changed since the last forecast.</li>
        <li>From T-48 h the EOC is at full activation, and more of the playbook applies.</li>
      </ol>
      <p className="hint">The forecasts are replayed in order; you can reset at any time.</p>
    </div>
  )
}
