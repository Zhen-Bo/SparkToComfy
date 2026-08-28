<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LORA_MAX, catalog, controls } from '@/stores/catalog'
import { loraCoverUrl } from '@/api/comfy'
import { cn } from '@/lib/utils'
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

function placePreview(e, file) {
  const d = coverDims.value[file] ?? { w: PREVIEW_MAX_W, h: PREVIEW_MAX_H }
  let left = e.clientX + CURSOR_GAP
  if (left + d.w + PAD + 8 > window.innerWidth) left = e.clientX - d.w - PAD - CURSOR_GAP
  const h = d.h + PAD
  const top = Math.min(Math.max(e.clientY - h / 2, 8), window.innerHeight - h - 8)
  preview.value = { file, left: Math.round(left), top: Math.round(top), w: d.w, h: d.h }
}
function showPreview(e, lora) {
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
  if (moveRAF) cancelAnimationFrame(moveRAF)
  moveRAF = 0
  lastMove = null
  preview.value = null
}
function onCoverError(file) {
  failed.value = new Set(failed.value).add(file)
}
/** Once the cover loads, measure its real ratio so the overlay hugs the image shape with no margins, and reposition once at the final size. */
function onCoverLoad(e, file) {
  const { naturalWidth: nw, naturalHeight: nh } = e.target
  if (!nw || !nh) return
  const r = nw / nh
  let w = PREVIEW_MAX_W
  let h = w / r
  if (h > PREVIEW_MAX_H) {
    h = PREVIEW_MAX_H
    w = h * r
  }
  coverDims.value = { ...coverDims.value, [file]: { w: Math.round(w), h: Math.round(h) } }
  if (preview.value?.file === file && lastMove) placePreview(lastMove, file)
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
          class="-mx-3 -mt-2.5 flex items-center justify-between gap-3 px-3 pt-2.5"
          @mouseenter="showPreview($event, lora)"
          @mousemove="movePreview"
          @mouseleave="hidePreview"
        >
          <span class="min-w-0 flex-1 truncate text-[12.5px] font-semibold" translate="no">{{ labelOf(lora.file) }}</span>
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
