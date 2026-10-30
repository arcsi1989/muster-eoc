import { useCallback, useLayoutEffect, useRef } from 'react'

type RefCallback = (node: HTMLElement | null) => void

/** The duration of the storm map's transitions, from the `--storm-transition` CSS property. */
function transitionMs(): number {
  const value = getComputedStyle(document.documentElement).getPropertyValue('--storm-transition').trim()
  const ms = value.endsWith('ms') ? parseFloat(value) : parseFloat(value) * 1000
  return Number.isFinite(ms) ? ms : 0
}

/** Animates list items from their old position to the new one when the order changes (FLIP),
 * so a reordered list moves in place, as long as the storm map's transition. Returns a stable
 * ref callback per item key. */
export function useFlip(order: string[]) {
  const nodes = useRef(new Map<string, HTMLElement>())
  const tops = useRef(new Map<string, number>())
  const refs = useRef(new Map<string, RefCallback>())
  const signature = order.join('\n')

  useLayoutEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const duration = transitionMs()
    for (const [key, node] of nodes.current) {
      const top = node.offsetTop
      const before = tops.current.get(key)
      tops.current.set(key, top)
      if (reduced || !duration || before === undefined || before === top || !node.animate) continue
      node.animate([{ transform: `translateY(${before - top}px)` }, { transform: 'none' }], {
        duration,
        easing: 'ease-out',
      })
    }
  }, [signature])

  return useCallback((key: string) => {
    let ref = refs.current.get(key)
    if (!ref) {
      ref = (node) => {
        if (node) nodes.current.set(key, node)
        else {
          nodes.current.delete(key)
          tops.current.delete(key)
          refs.current.delete(key)
        }
      }
      refs.current.set(key, ref)
    }
    return ref
  }, [])
}
