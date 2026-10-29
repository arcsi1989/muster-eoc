import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { CopilotPanel } from './CopilotPanel'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

function mockApi(chat: (body: { message: string; history: unknown[] }) => Response) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (String(input).endsWith('/clauses')) {
      return json([{ id: 'P-4.7', section: '4', title: 'Stop-work on wind (always in force)', text: 'No field work at a site where tropical-storm-force wind is forecast within 12 hours.' }])
    }
    return chat(JSON.parse(String(init?.body)))
  })
}

test('a suggested question gets an answer with clickable citations', async () => {
  mockApi(() =>
    json({
      answer: 'PS-14 Seawall Pumping Station is ranked 106 at advisory 3; stop-work P-4.7 applies from advisory 5.',
      citations: [{ id: 'PS-14', kind: 'asset' }, { id: 'P-4.7', kind: 'clause' }],
      provider: 'template',
      fallback: false,
      tools_used: ['explain_score'],
    }),
  )
  const onSelectAsset = vi.fn()
  render(<CopilotPanel onSelectAsset={onSelectAsset} />)

  await userEvent.click(screen.getByRole('button', { name: 'Why is PS-14 ranked where it is?' }))

  expect(await screen.findByText(/ranked 106 at advisory 3/)).toBeInTheDocument()
  expect(screen.getByText(/Offline answer · tools: explain_score/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'PS-14' }))
  expect(onSelectAsset).toHaveBeenCalledWith('PS-14')
  await userEvent.click(screen.getByRole('button', { name: 'P-4.7' }))
  expect(screen.getByRole('complementary', { name: 'Clause P-4.7' })).toHaveTextContent('No field work')
})

test('follow-up questions send the conversation so far', async () => {
  const fetchMock = mockApi(({ message }) =>
    json({ answer: `Answer to ${message}`, citations: [], provider: 'anthropic', fallback: false, tools_used: [] }),
  )
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.type(screen.getByLabelText('Ask the copilot'), 'First question')
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
  await screen.findByText('Answer to First question')
  await userEvent.type(screen.getByLabelText('Ask the copilot'), 'Second question')
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
  await screen.findByText('Answer to Second question')

  const last = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/copilot/chat')).at(-1)
  expect(JSON.parse(String(last?.[1]?.body)).history).toEqual([
    { role: 'user', content: 'First question' },
    { role: 'assistant', content: 'Answer to First question' },
  ])
  expect(screen.getAllByText('AI answer')).toHaveLength(2)
})

test('a failed request shows an error and keeps the question', async () => {
  mockApi(() => json({ error: { code: 'internal', message: 'database locked' } }, 500))
  render(<CopilotPanel onSelectAsset={() => {}} />)

  await userEvent.type(screen.getByLabelText('Ask the copilot'), 'What are the top risks?')
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('database locked')
  expect(screen.getByLabelText('Ask the copilot')).toHaveValue('What are the top risks?')
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
})
