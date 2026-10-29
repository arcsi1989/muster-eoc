import { useCallback, useLayoutEffect, useRef } from 'react'

type RefCallback = (node: HTMLElement | null) => void

/** Animates list items from their old position to the new one when the order changes (FLIP),
 * so a reordered list moves in place. Returns a stable ref callback per item key. */
export function useFlip(order: string[], durationMs = 300) {
  const nodes = useRef(new Map<string, HTMLElement>())
  const tops = useRef(new Map<string, number>())
  const refs = useRef(new Map<string, RefCallback>())
  const signature = order.join('\n')

  useLayoutEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    for (const [key, node] of nodes.current) {
      const top = node.offsetTop
      const before = tops.current.get(key)
      tops.current.set(key, top)
      if (reduced || before === undefined || before === top || !node.animate) continue
      node.animate([{ transform: `translateY(${before - top}px)` }, { transform: 'none' }], {
        duration: durationMs,
        easing: 'ease-out',
      })
    }
  }, [signature, durationMs])

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
