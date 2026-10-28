import { useSyncExternalStore } from 'react'

export type Route = 'operations' | 'data-quality'

function current(): Route {
  return window.location.hash === '#/data-quality' ? 'data-quality' : 'operations'
}

function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

/** Two routes don't need a router dependency: the hash picks the page. */
export function useHashRoute(): Route {
  return useSyncExternalStore(subscribe, current)
}
