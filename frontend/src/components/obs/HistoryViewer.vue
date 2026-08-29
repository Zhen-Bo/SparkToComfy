<script setup>
/* The history image viewer: the frame, the image-swap transition and keyboard routing.
   The zoom and pan geometry lives in lib/useZoomPan.js and copying in lib/useCopyImage.js;
   the parameter panel and the bottom dock are each their own component.

   Behaviour:
   - opening or switching fits the image (scale = minScale), the ceiling is 400% and the zoom factor is never displayed
   - left and right always switch images; panning is a drag once zoomed in, or Shift plus an arrow key; there are solid edge buttons plus the bottom dock
   - switching is a directional slide and cross-fade through a keyed remount inside a <Transition>, so the fit reset never runs through a transform transition and nothing jumps
   - the key hints and the parameter panel share one 264px column at the top left: one surface, one width, one left edge, with the panel collapsed by default
   - the column and the dock are translucent (.obs-ghost); restoring takes every parameter; a resize recomputes the floor */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useModalLayer } from '@/lib/useModalLayer'
import { useCopyImage } from '@/lib/useCopyImage'
import { PAN_STEP, ZOOM_FACTOR, useZoomPan } from '@/lib/useZoomPan'
import { useI18n } from 'vue-i18n'
import { sizeOf } from '@/stores/catalog'
import { restoreFromHistory, timeOf } from '@/stores/history'
import { locked } from '@/stores/run'
import { PhX, PhArrowSquareIn, PhCaretLeft, PhCaretRight, PhImageBroken } from '@phosphor-icons/vue'
import ViewerDock from '@/components/obs/ViewerDock.vue'
import ViewerParams from '@/components/obs/ViewerParams.vue'

const { t } = useI18n()

const props = defineProps({
  entries: { type: Array, required: true },
  startIndex: { type: Number, default: 0 },
})
const emit = defineEmits(['close'])

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
   The geometry comes from the file (DESIGN.md: the aspect ratio comes from the file). The preset is the reservation that draws the box before the image arrives, so the evidence never shifts, and the file takes over as it loads. */
const shownDims = computed(() => sizeOf(entry.value.workflowId, p.value.size))
const natural = ref(null)
const dims = computed(() => natural.value ?? shownDims.value ?? { width: 1, height: 1 })
function onImgLoad(e) {
  const { naturalWidth: w, naturalHeight: h } = e.target
  if (!w || !h) return
  const reservedWrongRatio = Math.abs(dims.value.width / dims.value.height - w / h) > 1e-3
  natural.value = { width: w, height: h }
  if (reservedWrongRatio) fitToStage() // the frame just changed shape, so the fit has to be taken again
}

/* A history entry can outlive its file: the record stays in the database after ComfyUI's output is cleared.
   The frame then keeps the preset shape and states the failure, the same rule the LoRA covers follow, so the browser never draws a broken-image icon.
   An entry that carries no image at all takes the same path, because there is no file to point the image element at. */
const failed = ref(false)
const src = computed(() => entry.value.images?.[0] ?? null)
const showImage = computed(() => !!src.value && !failed.value)

const {
  scale, dragging, pinching, gesturing, frameStyle, transform,
  fitToStage, zoom, panBy, onWheel, onPointerDown, onPointerMove, onPointerUp,
} = useZoomPan(dims)

const { toClipboard } = useCopyImage()
const copyImage = () => { if (showImage.value) toClipboard(src.value) } // nothing to put on the clipboard when the file is gone

/** Left and right always switch.
 * A switch resets to fit and plays the directional slide. */
function go(d) {
  slideDir.value = d
  natural.value = null // the next file reserves from its own preset, then corrects itself on load
  failed.value = false
  idx.value = (idx.value + d + props.entries.length) % props.entries.length
  fitToStage()
}

/** Focus loop: Tab stays inside the overlay, cycling between its first and last stop, a second guard beside inert.
 * The scrollable parameter list is a stop too, not only the buttons, so it cannot fall outside the loop. */
function cycleFocus(e) {
  const els = viewerRoot.value?.querySelectorAll('button:not([disabled]), [tabindex="0"]') ?? []
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

      <!-- Source order is reading order, so Tab follows the screen: the top-left column, the top-right actions,
           then the stage arrows, then the dock at the bottom. Stacking is set by z-index, not by this order. -->
      <!-- Top left: one column at one width, holding the key hints and then the parameter panel, collapsed by default.
           The hints carry only what the screen cannot show by itself: the wheel and the copy key. Switching, panning and closing each have their own visible cue.
           max-height keeps the column one gap clear of the previous button: 50vh is the button's centre, less half its 44px height, less the 16px gap, less the 20px top margin. -->
      <div
        class="obs-ghost pointer-events-auto absolute left-5 top-5 z-20 flex w-[264px] flex-col border border-hairline"
        style="max-height: calc(50vh - 58px)"
      >
        <div class="flex flex-none flex-wrap gap-x-4 gap-y-1 border-b border-hairline px-4 py-2.5 font-mono text-[12px] leading-[1.7] text-foreground">
          <span class="whitespace-nowrap">{{ t('viewer.hintWheel') }}</span>
          <span class="whitespace-nowrap">{{ t('viewer.hintCopy') }}</span>
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
                v-if="showImage"
                :src="src"
                class="h-full w-full border border-hairline bg-plate-bg object-contain"
                :alt="t('viewer.imgAlt', { n: idx + 1, width: dims.width, height: dims.height })"
                draggable="false"
                @load="onImgLoad"
                @error="failed = true"
              />
              <!-- The frame keeps the preset shape so the surrounding layout does not move, and says what happened instead of showing an empty box -->
              <div
                v-else
                class="flex h-full w-full flex-col items-center justify-center gap-3 border border-hairline bg-plate-bg px-6 text-center"
                role="img"
                :aria-label="t('errors.image_load_failed')"
              >
                <PhImageBroken class="h-10 w-10 text-ink-faint" aria-hidden="true" />
                <p class="text-[13px] text-muted-foreground">{{ t('errors.image_load_failed') }}</p>
              </div>
            </div>
          </div>
        </Transition>

        <button
          type="button"
          :title="t('viewer.prevTitle')"
          :aria-label="t('viewer.prev')"
          class="obs-tr absolute left-5 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-sm bg-[hsl(var(--edgeline))] text-foreground hover:bg-amber hover:text-[hsl(var(--primary-foreground))] active:scale-95"
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
</style>
