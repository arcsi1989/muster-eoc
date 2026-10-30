import { useSyncExternalStore } from 'react'

/** The pages, in nav order: one table drives the hash lookup and the nav links. */
export const PAGES = [
  { route: 'storm-map', hash: '#/', label: 'Storm map' },
  { route: 'operations', hash: '#/operations', label: 'Operations' },
  { route: 'field', hash: '#/field', label: 'Field tasks' },
  { route: 'audit', hash: '#/audit', label: 'Audit' },
  { route: 'data-quality', hash: '#/data-quality', label: 'Data quality' },
  { route: 'calibration', hash: '#/calibration', label: 'Calibration' },
] as const

export type Route = (typeof PAGES)[number]['route']

function current(): Route {
  return PAGES.find((p) => p.hash === window.location.hash)?.route ?? 'storm-map'
}

function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

/** A handful of pages don't need a router dependency: the hash picks the page. */
export function useHashRoute(): Route {
  return useSyncExternalStore(subscribe, current)
}
