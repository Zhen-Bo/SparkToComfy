<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LORA_MAX, catalog, controls } from '@/stores/catalog'
import { loraCoverUrl } from '@/api/comfy'
import { cn } from '@/lib/utils'
import { notify, notifyError } from '@/stores/notify'
import LoraPickerDialog from '@/components/obs/LoraPickerDialog.vue'
import Slider from '@/components/ui/Slider.vue'
import { PhImage, PhX } from '@phosphor-icons/vue'

const { t } = useI18n()

// The picker lives in LoraPickerDialog, shared with the /playground overview.
const open = ref(false)
// the add-LoRA button: where focus lands after a card is removed, and aria-disabled when full (see the template note)
const addBtn = ref(null)

const ctl = computed(() => controls.value.lora)
const options = computed(() => ctl.value?.options ?? {})
const strength = computed(() => ctl.value?.strength ?? { min: 0, max: 1, step: 0.05, default: 1 })
const picked = computed(() => catalog.params.lora ?? [])
const labelOf = (file) => options.value[file] ?? file

function setStrength(lora, v) {
  lora.strength = v[0]
}

/* The full hover preview follows the cursor.
   It is teleported to body and positioned fixed, because the panel is an overflow-y-auto scroll area that would clip an absolute overlay inside the component.
   It sits to the right of the cursor, flipping left when there is no room, and is clamped vertically to the window.
   Its size follows the real cover aspect ratio: the natural ratio is measured once the image loads and the overlay is repositioned, estimated at the maximum box until then. */
const PREVIEW_MAX_W = 320
const PREVIEW_MAX_H = 340
const PAD = 12 // total padding of the overlay, from p-1.5
const CURSOR_GAP = 14
const preview = ref(null) // { file, left, top, w, h }
const coverDims = ref({}) // file to { w, h }, filled in once img onload measures it
const failed = ref(new Set()) // file names whose cover 404s; the backend always answers not_found

/* The overlay waits half a second, so it does not flash when the cursor merely passes over a card.
   Cursor movement during the wait updates where it will appear. */
const SHOW_DELAY = 500
let showTimer = 0

function placePreview(e, file, forTouch = false) {
  const d = coverDims.value[file] ?? { w: PREVIEW_MAX_W, h: PREVIEW_MAX_H }
  const h = d.h + PAD
  let left
  if (forTouch) {
    // the finger would cover its own preview, so touch floats it centred above, not beside
    left = Math.min(Math.max(e.clientX - (d.w + PAD) / 2, 8), window.innerWidth - d.w - PAD - 8)
  } else {
    left = e.clientX + CURSOR_GAP
    if (left + d.w + PAD + 8 > window.innerWidth) left = e.clientX - d.w - PAD - CURSOR_GAP
  }
  const top = forTouch
    ? Math.min(Math.max(e.clientY - h - FINGER_GAP, 8), window.innerHeight - h - 8)
    : Math.min(Math.max(e.clientY - h / 2, 8), window.innerHeight - h - 8)
  preview.value = { file, left: Math.round(left), top: Math.round(top), w: d.w, h: d.h }
}
function showPreview(e, lora) {
  if (fromTouch()) return
  lastMove = { clientX: e.clientX, clientY: e.clientY }
  clearTimeout(showTimer)
  showTimer = setTimeout(() => {
    showTimer = 0
    if (lastMove) placePreview(lastMove, lora.file)
  }, SHOW_DELAY)
}
/* mousemove fires faster than the screen updates, so this computes at most once per frame and keeps only the last coordinates; the frames in between are never drawn.
   Coordinates are recorded even before the overlay appears, so the delay places it at the newest position. */
let moveRAF = 0
let lastMove = null
function movePreview(e) {
  if (fromTouch()) return
  lastMove = { clientX: e.clientX, clientY: e.clientY }
  if (!preview.value) return
  if (moveRAF) return
  moveRAF = requestAnimationFrame(() => {
    moveRAF = 0
    if (preview.value && lastMove) placePreview(lastMove, preview.value.file)
  })
}
function hidePreview() {
  if (showTimer) clearTimeout(showTimer)
  showTimer = 0
  if (pressTimer) clearTimeout(pressTimer)
  pressTimer = 0
  previewTouch = false
  pressFrom = null
  if (moveRAF) cancelAnimationFrame(moveRAF)
  moveRAF = 0
  lastMove = null
  preview.value = null
}

/* Long-press on the row: on the name it copies the name, anywhere else the cover floats above the finger.
   The row opts out of scrolling and the callout (see .lora-row), or the browser takes the gesture over halfway. */
const FINGER_GAP = 24 // the overlay floats this far above the finger, or the finger would cover it
let pressTimer = 0
let previewTouch = false
let pressFrom = null // { x, y, rect, file } of the hold start
let lastTouchAt = 0
// phones replay a touch as mouse events; the recency check keeps the hover path from double-firing
const fromTouch = () => Date.now() - lastTouchAt < 800

function onRowPointerDown(e, lora) {
  if (e.pointerType !== 'touch' || e.target.closest('button')) return
  lastTouchAt = Date.now()
  e.currentTarget.setPointerCapture(e.pointerId)
  pressFrom = { x: e.clientX, y: e.clientY, rect: e.currentTarget.getBoundingClientRect(), file: lora.file, onName: !!e.target.closest('.lora-name') }
  lastMove = { clientX: e.clientX, clientY: e.clientY }
  clearTimeout(pressTimer)
  pressTimer = setTimeout(() => {
    pressTimer = 0
    if (pressFrom.onName) return copyName(pressFrom.file)
    previewTouch = true
    placePreview(lastMove, pressFrom.file, true)
  }, SHOW_DELAY)
}

async function copyName(file) {
  const name = labelOf(file)
  try {
    await navigator.clipboard.writeText(name)
    notify(t('lora.copiedName', { name }))
  } catch (err) {
    console.error('[lora] failed to copy the name', err)
    notifyError(t('notify.copyDenied'))
  }
}

function updatePendingPress(e) {
  if (!pressTimer) return false
  if (Math.hypot(e.clientX - pressFrom.x, e.clientY - pressFrom.y) <= 12) return true
  clearTimeout(pressTimer)
  pressTimer = 0
  return true
}

const canMoveTouchPreview = () => previewTouch && !moveRAF
const hasTouchPreviewPosition = () => previewTouch && pressFrom && lastMove
const isInsidePressRow = ({ clientX, clientY }, rect) =>
  clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom

function moveTouchPreview() {
  moveRAF = 0
  if (!hasTouchPreviewPosition()) return
  if (isInsidePressRow(lastMove, pressFrom.rect)) placePreview(lastMove, pressFrom.file, true)
  else preview.value = null
}

function onRowPointerMove(e) {
  if (e.pointerType !== 'touch' || !pressFrom) return
  lastTouchAt = Date.now()
  lastMove = { clientX: e.clientX, clientY: e.clientY }
  // wandering before the hold finishes cancels the long-press
  if (updatePendingPress(e)) return
  if (!canMoveTouchPreview()) return
  moveRAF = requestAnimationFrame(moveTouchPreview)
}

function onRowPointerEnd(e) {
  if (e.pointerType !== 'touch') return
  clearTimeout(pressTimer)
  pressTimer = 0
  pressFrom = null
  if (previewTouch) {
    previewTouch = false
    preview.value = null
  }
}
function onCoverError(file) {
  failed.value = new Set(failed.value).add(file)
}

function fittedCoverSize(nw, nh) {
  const ratio = nw / nh
  let w = PREVIEW_MAX_W
  let h = w / ratio
  if (h <= PREVIEW_MAX_H) return { w: Math.round(w), h: Math.round(h) }
  h = PREVIEW_MAX_H
  w = h * ratio
  return { w: Math.round(w), h: Math.round(h) }
}

function repositionLoadedPreview(file) {
  if (preview.value?.file !== file || !lastMove) return
  placePreview(lastMove, file, previewTouch)
}

/** Once the cover loads, measure its real ratio so the overlay hugs the image shape with no margins, and reposition once at the final size. */
function onCoverLoad(e, file) {
  const { naturalWidth: nw, naturalHeight: nh } = e.target
  if (!nw || !nh) return
  coverDims.value = { ...coverDims.value, [file]: fittedCoverSize(nw, nh) }
  repositionLoadedPreview(file)
}
/* Being full does not use the native disabled attribute.
   When confirming the fifth LoRA closes the dialog, radix returns focus to this button, and native disabled would drop that focus onto body, the same evaporation problem as GenerateButton. aria-disabled plus this early return is enough. */
function openPicker() {
  if (picked.value.length >= LORA_MAX) return
  open.value = true
}
function remove(lora) {
  hidePreview() // mouseleave never fires once the card is gone, so close the overlay here
  catalog.params.lora = picked.value.filter((x) => x.file !== lora.file)
  // The remove button disappears with its card and keyboard focus would drop to body, so hand it to the add button, which is always there.
  nextTick(() => addBtn.value?.focus())
}
onBeforeUnmount(hidePreview) // same reason when switching tabs tears the component down
</script>

<template>
  <div>
    <div v-if="picked.length" class="flex flex-col gap-2">
      <div
        v-for="lora in picked"
        :key="lora.file"
        class="rounded-md border border-control obs-inset px-3 pb-3 pt-2.5"
      >
        <!-- Top row: the name on the left, with no description for a single name, the strength readout in amber on the right, and the remove button in the row.
             The remove button stays in the document flow, because hiding it would leave unexplained space.
             It is not absolutely positioned over the strength readout and it does not intercept this row's preview hover: an invisible button still takes pointer events and would kill hover across the top half.
             A cursor resting on the remove button means the intent is deletion, so the cover preview is suppressed there, closed on mouseenter and reopened on mouseleave.
             The row is items-center, so the text shares a centre line with the 24px button.
             The hover preview is bound to this row only, so moving down to the slider does not trigger it and adjusting strength is never covered by the overlay. -->
        <div
          class="lora-row -mx-3 -mt-2.5 flex select-none items-center justify-between gap-3 px-3 pt-2.5"
          @mouseenter="showPreview($event, lora)"
          @mousemove="movePreview"
          @mouseleave="hidePreview"
          @pointerdown="onRowPointerDown($event, lora)"
          @pointermove="onRowPointerMove"
          @pointerup="onRowPointerEnd"
          @pointercancel="onRowPointerEnd"
          @contextmenu.prevent
        >
          <span class="lora-name min-w-0 flex-1 truncate text-[12.5px] font-semibold" translate="no">{{ labelOf(lora.file) }}</span>
          <span class="shrink-0 font-mono text-[13px] font-semibold text-amber-bright tabular-nums" translate="no">{{ lora.strength.toFixed(2) }}</span>
          <button
            type="button"
            :title="t('lora.remove', { name: labelOf(lora.file) })"
            :aria-label="t('lora.remove', { name: labelOf(lora.file) })"
            class="obs-tr flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-control bg-plate text-ink-faint hover:border-destructive/60 hover:text-destructive active:scale-95"
            @click="remove(lora)"
            @mouseenter="hidePreview"
            @mouseleave="showPreview($event, lora)"
          >
            <PhX class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>

          <div class="mt-2 flex h-5 items-center">
          <Slider
            :model-value="[lora.strength]"
            :min="strength.min"
            :max="strength.max"
            :step="strength.step"
            :aria-label="t('lora.strength', { name: labelOf(lora.file) })"
            @update:model-value="setStrength(lora, $event)"
          />
        </div>
      </div>
    </div>

    <button
      type="button"
      ref="addBtn"
      :aria-disabled="picked.length >= LORA_MAX"
      :class="cn(
        'obs-tr mt-2 w-full rounded-md border border-dashed py-2 text-[12px] tracking-[.1em]',
        picked.length >= LORA_MAX
          ? 'cursor-not-allowed border-control/50 text-ink-faint opacity-50'
          : 'border-control text-muted-foreground hover:border-amber hover:text-amber active:scale-[.98]',
      )"
      @click="openPicker"
    >{{ t('lora.add') }}</button>

    <LoraPickerDialog v-model:open="open" />

    <!-- Full hover preview: fixed and following the cursor, taking no layout space, with the box at the real cover ratio and no margins -->
    <Teleport to="body">
      <div
        v-if="preview"
        class="obs-elevated pointer-events-none fixed z-[60] animate-fade-in rounded-md border border-hairline p-1.5 shadow-[0_18px_48px_-12px_hsl(var(--dome)/.9)]"
        :style="{ left: `${preview.left}px`, top: `${preview.top}px` }"
      >
        <div
          class="flex items-center justify-center overflow-hidden rounded-sm bg-plate-bg"
          :style="{ width: `${preview.w}px`, height: `${preview.h}px` }"
        >
          <img
            v-if="!failed.has(preview.file)"
            :src="loraCoverUrl(preview.file)"
            :alt="t('lora.cover', { name: labelOf(preview.file) })"
            class="h-full w-full object-contain"
            @load="onCoverLoad($event, preview.file)"
            @error="onCoverError(preview.file)"
          />
          <!-- Placeholder for a 404 cover, so the browser never draws a broken-image icon -->
          <PhImage v-else class="h-10 w-10 text-ink-faint" aria-hidden="true" />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* The row doubles as the long-press surface for the cover preview, so it cannot also start a scroll or a text selection. */
.lora-row {
  touch-action: none;
  -webkit-touch-callout: none;
}
</style>
