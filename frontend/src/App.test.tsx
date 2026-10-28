import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import App from './App'

test('counter increments when clicked', async () => {
  render(<App />)

  await userEvent.click(screen.getByRole('button', { name: /count is 0/i }))

  expect(screen.getByRole('button', { name: /count is 1/i })).toBeInTheDocument()
})
