import type { Advisory, Scenario } from '../../types/scenario'

/** The current advisory as the backend names it in the scenario state, and the one before it.
 * Nothing while the scenario is loading. */
export function currentAdvisories(scenario: Scenario | null): {
  currentNo: number
  current: Advisory | undefined
  previous: Advisory | undefined
} {
  const byNo = (no: number) => scenario?.advisories.find((a) => a.advisory_no === no)
  const currentNo = scenario?.current_advisory ?? 0
  return { currentNo, current: byNo(currentNo), previous: byNo(currentNo - 1) }
}
