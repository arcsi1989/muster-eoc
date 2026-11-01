import type { CopilotStep } from '../../types/scenario'

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${value === null ? 'current' : JSON.stringify(value)}`)
    .join(', ')
}

/** A tool call as a person reads it: `explain_score(asset_id: "PS-14", advisory: current)`. */
export function toolCallLabel(name: string, args: Record<string, unknown>): string {
  return `${name}(${formatArgs(args)})`
}

/** One progress step in words. A step never carries answer text, only what was done. */
export function stepLabel(step: CopilotStep): string {
  switch (step.kind) {
    case 'attempt':
      return step.attempt === 1 ? `Asking ${step.provider}` : `Retrying: attempt ${step.attempt} with ${step.provider}`
    case 'tool_call':
      return `Called ${toolCallLabel(step.tool ?? 'a tool', step.args)}`
    case 'validating':
      return 'Validating the answer: every ID and number must come from a tool'
    case 'validated':
      return 'Validated'
    case 'rejected':
      return `Rejected: ${step.problems.join('; ')}`
    case 'failed':
      return `${step.provider} failed: ${step.reason ?? 'no reason given'}`
    case 'fallback':
      return `Falling back to the template: ${step.reason ?? 'no reason given'}`
  }
}
