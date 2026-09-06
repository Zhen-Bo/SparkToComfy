import { nextTick, onMounted, onUnmounted } from 'vue'

/* Reference-count inert so closing one overlay cannot unlock the background of another.
   Callers own keyboard handling and returning focus to the opener. */
let depth = 0

export function useModalLayer(focusTarget) {
  const appEl = typeof document !== 'undefined' ? document.getElementById('app') : null
  onMounted(() => {
    if (depth === 0) appEl?.setAttribute('inert', '')
    depth += 1
    nextTick(() => focusTarget?.value?.focus())
  })
  onUnmounted(() => {
    depth = Math.max(0, depth - 1)
    if (depth === 0) appEl?.removeAttribute('inert')
  })
}
