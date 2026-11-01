export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function failure(res: Response): Promise<ApiError> {
  const body: unknown = await res.json().catch(() => null)
  const error = (body as { error?: { code?: string; message?: string } } | null)?.error
  return new ApiError(res.status, error?.code ?? 'unknown', error?.message ?? res.statusText)
}

/** The only place that calls fetch (CODING_STANDARDS F1). Paths are proxied to the backend. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers },
  })
  if (!res.ok) throw await failure(res)
  return (await res.json().catch(() => null)) as T
}

export interface StreamEvent {
  event: string
  data: unknown
}

/** One server-sent event block ("event: x" and "data: {...}" lines) as an event and its data. */
function parseEvent(block: string): StreamEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
  }
  return data.length ? { event, data: JSON.parse(data.join('\n')) as unknown } : null
}

/** POSTs and reads the server-sent events of the response as they arrive, calling `onEvent` for
 * each. A failed request rejects with the same ApiError as `api`. */
export async function streamEvents(path: string, body: unknown, onEvent: (event: StreamEvent) => void): Promise<void> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw await failure(res)
  if (!res.body) throw new ApiError(res.status, 'stream_failed', 'The response has no body')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = done ? '' : (blocks.pop() ?? '')
    for (const block of blocks) {
      const parsed = parseEvent(block)
      if (parsed) onEvent(parsed)
    }
    if (done) return
  }
}
