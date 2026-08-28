import { nextTick, onMounted, onUnmounted } from 'vue'

/**
 * The two things every overlay shares: `#app` behind it goes inert while it is open, and focus enters the overlay as it opens.
 *
 * Returning focus is not handled here, because only the opener knows where it belongs (a history card, the clear button, and so on).
 * Neither is the keyboard contract: the meaning of ESC and the Tab loop differ from overlay to overlay.
 *
 * inert is refcounted rather than set and unset.
 * With two overlays open at once, the first one to unmount would otherwise strip inert from the one still open and make the background tabbable again.
 * The count means only the last layer to close unlocks it.
*/
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
