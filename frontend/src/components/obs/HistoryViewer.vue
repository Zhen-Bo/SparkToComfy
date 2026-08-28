<script setup>
/* The history image viewer: the frame, the image-swap transition and keyboard routing.
   The zoom and pan geometry lives in lib/useZoomPan.js and copying in lib/useCopyImage.js;
   the parameter panel and the bottom dock are each their own component.

   Behaviour:
   - opening or switching fits the image (scale = minScale), the ceiling is 400% and the zoom factor is never displayed
   - left and right always switch images; panning is a drag once zoomed in, or Shift plus an arrow key; there are solid edge buttons plus the bottom dock
   - switching is a directional slide and cross-fade through a keyed remount inside a <Transition>, so the fit reset never runs through a transform transition and nothing jumps
   - the caption row stays minimal (wheel to zoom, 0 to reset, ESC to close), with no detailed mode and no count; the parameter panel is collapsed by default below it
   - the caption row, parameters and dock are translucent (.obs-ghost); restoring takes every parameter; a resize recomputes the floor */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useModalLayer } from '@/lib/useModalLayer'
import { useCopyImage } from '@/lib/useCopyImage'
import { PAN_STEP, ZOOM_FACTOR, useZoomPan } from '@/lib/useZoomPan'
import { useI18n } from 'vue-i18n'
import { sizeOf } from '@/stores/catalog'
import { restoreFromHistory, timeOf } from '@/stores/history'
import { locked } from '@/stores/run'
import { PhX, PhArrowSquareIn, PhCaretLeft, PhCaretRight } from '@phosphor-icons/vue'
import ViewerDock from '@/components/obs/ViewerDock.vue'
import ViewerParams from '@/components/obs/ViewerParams.vue'

const { t } = useI18n()

const props = defineProps({
  entries: { type: Array, required: true },
  startIndex: { type: Number, default: 0 },
})
const emit = defineEmits(['close'])

// How far the previous button steps aside when the parameter panel is open: the panel sits at left-5 and is 264px wide, so its right edge is at 284px, plus a 16px gap.
const PANEL_CLEAR = 280

const idx = ref(props.startIndex)
const paramsOpen = ref(false)
// swap direction: 1 is next, the old image leaving left; -1 is previous, the old image leaving right
const slideDir = ref(1)
const closeBtn = ref(null)
const viewerRoot = ref(null)

const entry = computed(() => props.entries[idx.value])
const p = computed(() => entry.value.params)

/* The size has two uses with different sources.
   The readout must be honest: an unknown preset shows a dash rather than an invented 1x1.
   The geometry still needs something to draw with, so it falls back to the natural size of the image file (DESIGN.md: the aspect ratio comes from the file). */
const shownDims = computed(() => sizeOf(entry.value.workflowId, p.value.size))
const natural = ref(null)
const dims = computed(() => shownDims.value ?? natural.value ?? { width: 1, height: 1 })
function onImgLoad(e) {
  const { naturalWidth: w, naturalHeight: h } = e.target
  if (w && h) natural.value = { width: w, height: h }
}

const {
  scale, dragging, pinching, gesturing, frameStyle, transform,
  fitToStage, zoom, panBy, onWheel, onPointerDown, onPointerMove, onPointerUp,
} = useZoomPan(dims)

const { toClipboard } = useCopyImage()
const copyImage = () => toClipboard(entry.value.images[0])

/** Left and right always switch.
 * A switch resets to fit and plays the directional slide. */
function go(d) {
  slideDir.value = d
  idx.value = (idx.value + d + props.entries.length) % props.entries.length
  fitToStage()
}

/** Focus loop: Tab stays inside the overlay, cycling between the first and last button, a second guard beside inert. */
function cycleFocus(e) {
  const els = viewerRoot.value?.querySelectorAll('button:not([disabled])') ?? []
  if (!els.length) return
  const active = document.activeElement
  const inside = viewerRoot.value?.contains(active)
  if (e.shiftKey && (!inside || active === els[0])) { e.preventDefault(); els[els.length - 1].focus() }
  else if (!e.shiftKey && (!inside || active === els[els.length - 1])) { e.preventDefault(); els[0].focus() }
}

/** Shift plus an arrow key pans once zoomed in.
 * Unmodified left and right still switch images. */
function panWithArrows(key) {
  if (key === 'ArrowLeft') panBy(PAN_STEP, 0)
  if (key === 'ArrowRight') panBy(-PAN_STEP, 0)
  if (key === 'ArrowUp') panBy(0, PAN_STEP)
  if (key === 'ArrowDown') panBy(0, -PAN_STEP)
}

/* Unmodified keys, each one its own entry.
   Only the arrows take preventDefault, because only they collide with a browser default (scrolling the page). */
const KEYS = {
  Escape: () => emit('close'),
  Tab: cycleFocus,
  ArrowLeft: (e) => { e.preventDefault(); go(-1) },
  ArrowRight: (e) => { e.preventDefault(); go(1) },
  '+': () => zoom(ZOOM_FACTOR),
  '=': () => zoom(ZOOM_FACTOR),
  '-': () => zoom(1 / ZOOM_FACTOR),
  '_': () => zoom(1 / ZOOM_FACTOR),
  '0': fitToStage,
}

function onKeydown(e) {
  // Ctrl or Cmd plus C copies the current image to the system clipboard, matching the browser right-click "copy image" convention
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
    e.preventDefault()
    return copyImage()
  }
  if (e.shiftKey && scale.value > 1 && e.key.startsWith('Arrow')) {
    e.preventDefault()
    return panWithArrows(e.key)
  }
  KEYS[e.key]?.(e)
}

// Accessibility: the background goes inert on open and focus moves to the close button.
// After closing, HistoryRail returns focus to the card that opened it.
useModalLayer(closeBtn)
onMounted(() => {
  fitToStage() // fit as soon as it opens
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))

/* No restoring while generating, for the same reason as RatioSelector and the workflow dropdown.
   It uses aria-disabled rather than disabled so focus does not evaporate onto body, and restoreFromHistory guards itself too, because this overlay is not the only way in. */
function backfill() {
  if (locked.value) return
  restoreFromHistory(entry.value)
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      ref="viewerRoot"
      class="viewer-root fixed inset-0 z-[200] overscroll-contain"
      :class="{ 'bd-off': gesturing }"
      role="dialog"
      aria-modal="true"
      :aria-label="t('viewer.aria')"
      @wheel="onWheel"
    >
      <div class="absolute inset-0 bg-overlay/90" :class="gesturing ? '' : 'backdrop-blur-[3px]'" />

      <div class="sr-only" aria-live="polite">{{ t('viewer.counter', { n: idx + 1, total: entries.length }) }}</div>

      <!-- Stage: full bleed, with the margins on all four sides handled by the fit maths.
           A click anywhere outside the image closes it -->
      <div
        class="absolute inset-0 flex items-center justify-center"
        style="touch-action: none"
        @click="emit('close')"
      >
        <!-- Swap transition: a keyed remount plus a directional slide and cross-fade.
             The new node mounts already fitted, so the fit reset never runs through a transform transition and nothing jumps -->
        <Transition :name="slideDir > 0 ? 'swap-next' : 'swap-prev'" mode="out-in">
          <div :key="idx" class="swap-item">
            <div
              class="obs-corners select-none"
              :style="{
                ...frameStyle,
                transform,
                cursor: scale > 1 ? (dragging || pinching ? 'grabbing' : 'grab') : 'default',
                transition: dragging || pinching ? 'none' : 'transform 90ms linear',
              }"
              @click.stop
              @pointerdown="onPointerDown"
              @pointermove="onPointerMove"
              @pointerup="onPointerUp"
              @pointercancel="onPointerUp"
              @lostpointercapture="onPointerUp"
            >
              <img
                :src="entry.images[0]"
                class="h-full w-full border border-hairline bg-plate-bg object-contain"
                :alt="t('viewer.imgAlt', { n: idx + 1, width: dims.width, height: dims.height })"
                draggable="false"
                @load="onImgLoad"
              />
            </div>
          </div>
        </Transition>

        <button
          type="button"
          :title="t('viewer.prevTitle')"
          :aria-label="t('viewer.prev')"
          class="nav-edge obs-tr absolute left-5 top-1/2 z-20 flex h-11 w-11 items-center justify-center rounded-sm bg-[hsl(var(--edgeline))] text-foreground hover:bg-amber hover:text-[hsl(var(--primary-foreground))] active:scale-95"
          :style="{ transform: 'translateY(-50%) translateX(' + (paramsOpen ? PANEL_CLEAR : 0) + 'px)' }"
          @click.stop="go(-1)"
        ><PhCaretLeft class="h-[18px] w-[18px]" aria-hidden="true" /></button>
        <button
          type="button"
          :title="t('viewer.nextTitle')"
          :aria-label="t('viewer.next')"
          class="obs-tr absolute right-5 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-sm bg-[hsl(var(--edgeline))] text-foreground hover:bg-amber hover:text-[hsl(var(--primary-foreground))] active:scale-95"
          @click.stop="go(1)"
        ><PhCaretRight class="h-[18px] w-[18px]" aria-hidden="true" /></button>
      </div>

      <ViewerDock
        :index="idx"
        :total="entries.length"
        :time="timeOf(entry.finishedAt)"
        @go="go"
        @close="emit('close')"
      />

      <!-- Top left: the minimal caption row (wheel, 0, Ctrl+C, ESC) plus the parameter panel, pinned below it and collapsed by default -->
      <div class="pointer-events-none absolute left-5 top-5 z-20 flex flex-col items-start gap-3">
        <div class="obs-ghost pointer-events-auto flex items-center gap-3 whitespace-nowrap border border-hairline px-4 py-2 font-mono text-[12px] text-foreground">
          <span>{{ t('viewer.hintWheel') }}</span>
          <span class="text-muted-foreground">・</span>
          <span>{{ t('viewer.hintReset') }}</span>
          <span class="text-muted-foreground">・</span>
          <span>{{ t('viewer.hintCopy') }}</span>
          <span class="text-muted-foreground">・</span>
          <span>{{ t('viewer.hintClose') }}</span>
        </div>

        <ViewerParams v-model="paramsOpen" :params="p" :shown-dims="shownDims" />
      </div>

      <div class="absolute right-5 top-5 z-20 flex flex-col gap-2.5">
        <!-- Close is a leaving action, so hover only brightens it neutrally.
             Amber is reserved for the CTA, the active state and readouts -->
        <button
          ref="closeBtn"
          type="button"
          :title="t('viewer.close')"
          :aria-label="t('viewer.close')"
          class="obs-tr flex h-11 w-11 items-center justify-center rounded-sm bg-[hsl(var(--edgeline))] text-foreground hover:shadow-[inset_0_0_0_999px_hsl(var(--foreground)/.12)] active:scale-95"
          @click="emit('close')"
        ><PhX class="h-[18px] w-[18px]" aria-hidden="true" /></button>
        <button
          type="button"
          :title="t('viewer.backfill')"
          :aria-label="t('viewer.backfill')"
          :aria-disabled="locked || undefined"
          class="obs-tr flex h-11 w-11 items-center justify-center rounded-sm bg-amber text-[hsl(var(--primary-foreground))] shadow-[0_2px_10px_hsl(var(--amber)/.3)] active:scale-95"
          :class="locked ? 'cursor-not-allowed opacity-40 shadow-none' : 'hover:bg-amber-bright'"
          @click="backfill"
        ><PhArrowSquareIn class="h-[18px] w-[18px]" aria-hidden="true" /></button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* The swap slide: next sends the old image out left and brings the new one in from the right, previous reverses it.
   Both directions animate the wrapper only, never the transform on the image frame itself. */
.swap-next-enter-active,
.swap-next-leave-active,
.swap-prev-enter-active,
.swap-prev-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}
.swap-next-leave-active,
.swap-prev-leave-active {
  pointer-events: none;
}
.swap-next-enter-from {
  opacity: 0;
  transform: translateX(28px);
}
.swap-next-leave-to {
  opacity: 0;
  transform: translateX(-28px);
}
.swap-prev-enter-from {
  opacity: 0;
  transform: translateX(-28px);
}
.swap-prev-leave-to {
  opacity: 0;
  transform: translateX(28px);
}

/* The overlay enters with opacity plus a .98 scale from the centre; the backdrop blur is constant and never transitions.
   Closing is handled by <Transition name="viewer"> in HistoryRail, and its 140ms exit is faster than the entry.
   During the exit, animation: none drops the fill, or the frozen end values of the entry keyframe would override the exit transition. */
.viewer-root { animation: viewerIn .2s var(--ease-fluid) both; }
@keyframes viewerIn {
  from { opacity: 0; transform: scale(.98); }
  to   { opacity: 1; transform: scale(1); }
}
.viewer-leave-active { animation: none; transition: opacity 140ms ease-out, transform 140ms ease-out; pointer-events: none; }
.viewer-leave-to     { opacity: 0; transform: scale(.98); }

/* The previous button steps aside with a transform only, so it runs on the compositor.
   Reduced motion is collapsed to nearly instant by the global rule in style.css. */
.nav-edge { transition: transform .18s var(--ease-fluid); }
</style>
