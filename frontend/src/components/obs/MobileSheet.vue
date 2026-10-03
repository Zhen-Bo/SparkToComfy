<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { run } from '@/stores/run'
import { catalog, controls } from '@/stores/catalog'
import { PhCaretDown, PhPencilSimple } from '@phosphor-icons/vue'
import ParameterFields from '@/components/obs/ParameterFields.vue'
import OfflineOverlay from '@/components/obs/OfflineOverlay.vue'

const { t } = useI18n()

/* The collapsed strip is a summary of the current settings, so the drawer reads as more than an empty bar.
   Its height is measured rather than fixed, since the text inside follows the user's font size. */
const grab = ref(null)
const stripH = ref(0) // the summary row plus the body's top hairline

const sheet = ref(null)
const sheetH = ref(0)
/** translateY in px: 0 is expanded, maxTy is collapsed. */
const ty = ref(0)
const dragging = ref(false)
const expanded = defineModel('expanded', { type: Boolean, default: false })

const maxTy = computed(() => Math.max(0, sheetH.value - stripH.value))

let ro = null
onMounted(() => {
  ro = new ResizeObserver(() => {
    sheetH.value = sheet.value.getBoundingClientRect().height
    stripH.value = grab.value.offsetHeight + 1
    if (!dragging.value) ty.value = expanded.value ? 0 : maxTy.value
  })
  ro.observe(sheet.value)
  ro.observe(grab.value)
})

const prompt = computed(() => String(catalog.params.positive ?? '').replace(/\s+/g, ' ').trim())
const hasPrompt = computed(() => 'positive' in controls.value)
const optionLabel = (ctl, value) => {
  const o = ctl?.options?.[value]
  return typeof o === 'string' ? o : o?.label ?? value
}
// Only the settings that change the picture's shape or character; each appears only if the workflow declares it
const chips = computed(() => {
  const c = controls.value
  const p = catalog.params
  const out = []
  const preset = c.size?.presets?.[p.size?.preset]
  if (preset) {
    const [a, b] = String(preset.label).split(':')
    out.push(p.size.landscape && b ? `${b}:${a}` : preset.label)
    out.push(t(p.size.highres ? 'ratio.highres' : 'ratio.standard'))
  }
  if (c.steps) out.push(t('sheet.steps', { n: p.steps }))
  if (c.sampler) out.push(optionLabel(c.sampler, p.sampler))
  if (c.lora && p.lora?.length) out.push(`LoRA ${p.lora.length}`)
  return out
})
onUnmounted(() => ro?.disconnect())

let startTy = 0
let startY = 0
let moved = false
let trail = [] // last few [time, clientY] samples for release velocity

function onPointerDown(e) {
  if (e.button !== undefined && e.button !== 0) return
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
  if (!moved) return snapTo(expanded.value ? maxTy.value : 0)

  const [t0, y0] = trail[0]
  const dt = Math.max(1, e.timeStamp - t0)
  const v = ((e.clientY - y0) / dt) * 1000 // px/s, positive = downward = closing
  // Project remaining travel with exponential decay (d = 0.998), then snap to the nearer boundary.
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

defineExpose({ el: sheet, expanded, collapse, stripH })
</script>

<template>
  <section
    ref="sheet"
    :aria-label="t('panel.aria')"
    class="obs-panel absolute inset-x-0 bottom-0 z-30 flex h-[95%] flex-col border-t border-edgeline shadow-[0_-8px_24px_rgba(0,0,0,.55)] will-change-transform"
    :class="dragging ? 'transition-none' : 'transition-transform duration-[380ms] ease-[var(--ease-fluid)]'"
    :style="{ transform: `translateY(${ty}px)` }"
  >
    <!-- Pointer taps toggle in onPointerUp; keyboard presses arrive as detail-0 clicks and toggle in @click -->
    <button
      ref="grab"
      type="button"
      class="flex w-full flex-none cursor-grab touch-none flex-col items-stretch gap-1 px-4 pb-2.5 pt-1.5 text-left active:cursor-grabbing"
      :aria-expanded="expanded"
      :aria-label="t(expanded ? 'sheet.collapse' : 'sheet.expand')"
      aria-describedby="mobile-sheet-summary"
      aria-controls="mobile-sheet-body"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @click="$event.detail === 0 && snapTo(expanded ? maxTy : 0)"
      @keydown.escape="collapse()"
    >
      <span class="h-[5px] w-9 self-center rounded-full bg-control" aria-hidden="true" />
      <!-- Both faces share one box, so the strip keeps its height and only the content crossfades -->
      <span class="grid">
        <span
          id="mobile-sheet-summary"
          class="col-start-1 row-start-1 flex min-w-0 flex-col gap-1 transition-opacity duration-200"
          :class="expanded && 'opacity-0'"
        >
          <span v-if="hasPrompt && prompt" class="truncate text-[13px] leading-snug text-foreground" translate="no">{{ prompt }}</span>
          <span v-else-if="hasPrompt" class="flex items-center gap-1.5 text-[13px] leading-snug text-amber-bright">
            <PhPencilSimple class="h-3.5 w-3.5 flex-none" aria-hidden="true" />{{ t('sheet.promptEmpty') }}
          </span>
          <span class="truncate font-mono text-[11px] leading-snug text-ink-faint tabular-nums" translate="no">{{ chips.join(' · ') }}</span>
        </span>
        <span
          class="col-start-1 row-start-1 flex items-center justify-between self-center transition-opacity duration-200"
          :class="!expanded && 'opacity-0'"
          aria-hidden="true"
        >
          <span class="text-[13px] font-bold tracking-[.1em] text-foreground">{{ t('sheet.title') }}</span>
          <PhCaretDown class="h-4 w-4 text-muted-foreground" />
        </span>
      </span>
    </button>

    <!-- Sheet body; the offline overlay anchors here and leaves the grabber reachable -->
    <div id="mobile-sheet-body" class="relative flex min-h-0 flex-1 flex-col border-t border-hairline">
      <ParameterFields />
      <OfflineOverlay />
    </div>
  </section>
</template>
