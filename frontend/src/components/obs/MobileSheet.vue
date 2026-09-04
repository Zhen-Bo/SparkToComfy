<script setup>
/** The mobile parameter sheet: one grabber, two snap points (collapsed to the grabber, expanded over the stage). */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { run } from '@/stores/run'
import ParameterFields from '@/components/obs/ParameterFields.vue'
import OfflineOverlay from '@/components/obs/OfflineOverlay.vue'

const { t } = useI18n()

const GRAB_H = 21 // the collapsed strip: the grabber row plus the top hairline

const sheet = ref(null)
const sheetH = ref(0)
/** translateY in px: 0 is expanded, maxTy is collapsed. */
const ty = ref(0)
const dragging = ref(false)
const expanded = defineModel('expanded', { type: Boolean, default: false })

const maxTy = computed(() => Math.max(0, sheetH.value - GRAB_H))

let ro = null
onMounted(() => {
  ro = new ResizeObserver(([entry]) => {
    sheetH.value = entry.contentRect.height
    // resizes re-anchor the parked state
    ty.value = expanded.value ? 0 : maxTy.value
  })
  ro.observe(sheet.value)
})
onUnmounted(() => ro?.disconnect())

let startTy = 0
let startY = 0
let moved = false
let trail = [] // last few [time, clientY] samples for release velocity

function onPointerDown(e) {
  if (e.button !== undefined && e.button !== 0) return
  // capture on the button: the move/up handlers live here
  e.currentTarget.setPointerCapture(e.pointerId)
  /* A press mid-settle interrupts it: ty already holds the target, so the live position comes from the rendered rect, not the ref. */
  const parentBottom = sheet.value.offsetParent?.getBoundingClientRect().bottom
  const liveTy = parentBottom == null
    ? NaN
    : sheet.value.getBoundingClientRect().top - (parentBottom - sheetH.value)
  startTy = Number.isFinite(liveTy) ? Math.min(Math.max(liveTy, 0), maxTy.value) : ty.value
  startY = e.clientY
  moved = false
  dragging.value = true
  trail = [[e.timeStamp, e.clientY]]
}

function onPointerMove(e) {
  if (!dragging.value) return
  const dy = e.clientY - startY
  if (Math.abs(dy) > 6) moved = true // hysteresis: a tap is not a drag
  trail.push([e.timeStamp, e.clientY])
  if (trail.length > 5) trail.shift()
  const next = startTy + dy
  ty.value = Math.min(Math.max(next, 0), maxTy.value)
}

function onPointerUp(e) {
  if (!dragging.value) return
  dragging.value = false
  e.currentTarget.releasePointerCapture?.(e.pointerId)
  // A tap on the grabber toggles the sheet.
  if (!moved) return snapTo(expanded.value ? maxTy.value : 0)

  const [t0, y0] = trail[0]
  const dt = Math.max(1, e.timeStamp - t0)
  const v = ((e.clientY - y0) / dt) * 1000 // px/s, positive = downward = closing
  // flick projection (Apple's exponential decay, d = 0.998), then snap to the nearer boundary
  const projected = ty.value + (v / 1000) * (0.998 / (1 - 0.998))
  snapTo(Math.abs(projected - 0) < Math.abs(projected - maxTy.value) ? 0 : maxTy.value)
}

function snapTo(target) {
  expanded.value = target === 0
  ty.value = target
}

function collapse() {
  if (sheetH.value) snapTo(maxTy.value)
}

// a run locks the parameters anyway, so the sheet folds down to the stage preview
watch(() => run.busy, (busy) => {
  if (busy) collapse()
})

defineExpose({ el: sheet, expanded, collapse })
</script>

<template>
  <!-- Reduced motion needs no branch: the global reduce rule strips transform transitions -->
  <section
    ref="sheet"
    :aria-label="t('panel.aria')"
    class="obs-panel absolute inset-x-0 bottom-0 z-30 flex h-[95%] flex-col border-t border-edgeline shadow-[0_-8px_24px_rgba(0,0,0,.55)] will-change-transform"
    :class="dragging ? 'transition-none' : 'transition-transform duration-[380ms] ease-[var(--ease-fluid)]'"
    :style="{ transform: `translateY(${ty}px)` }"
  >
    <!-- Pointer taps toggle in onPointerUp; keyboard presses arrive as detail-0 clicks and toggle in @click -->
    <button
      type="button"
      class="flex h-5 w-full flex-none cursor-grab touch-none items-start justify-center pt-1.5 active:cursor-grabbing"
      :aria-expanded="expanded"
      :aria-label="t(expanded ? 'sheet.collapse' : 'sheet.expand')"
      aria-controls="mobile-sheet-body"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @click="$event.detail === 0 && snapTo(expanded ? maxTy : 0)"
      @keydown.escape="collapse()"
    >
      <span class="h-[5px] w-9 rounded-full bg-control" aria-hidden="true" />
    </button>

    <!-- Sheet body; the offline overlay anchors here and leaves the grabber reachable -->
    <div id="mobile-sheet-body" class="relative flex min-h-0 flex-1 flex-col border-t border-hairline">
      <ParameterFields />
      <OfflineOverlay />
    </div>
  </section>
</template>
