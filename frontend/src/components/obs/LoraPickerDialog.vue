<script setup>
// Draft selection and strengths are committed together only on confirm.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { LORA_MAX, catalog, controls } from '@/stores/catalog'
import { loraCoverUrl } from '@/api/comfy'
import { cn } from '@/lib/utils'
import Dialog from '@/components/ui/Dialog.vue'
import Slider from '@/components/ui/Slider.vue'
import { PhCheck, PhImage, PhMagnifyingGlass, PhX } from '@phosphor-icons/vue'

const { t } = useI18n()
const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['update:open'])
const ctl = computed(() => controls.value.lora)
const options = computed(() => ctl.value?.options ?? {})
const files = computed(() => Object.keys(options.value))
const labelOf = (file) => options.value[file] ?? file
const strengthCtl = computed(() => ctl.value?.strength ?? { min: 0, max: 1, step: 0.05, default: 1 })
const sel = ref([])
const selOf = (file) => sel.value.find(s => s.file === file)
const full = computed(() => sel.value.length >= LORA_MAX)
const failed = ref(new Set())
const q = ref('')
const onlySelected = ref(false)
const sidebar = ref(null)
const shown = computed(() => {
  const needle = q.value.trim().toLocaleLowerCase()
  return files.value.filter(file => (!onlySelected.value || selOf(file)) &&
    `${labelOf(file)} ${file}`.toLocaleLowerCase().includes(needle))
})
watch(() => props.open, v => {
  if (v) {
    sel.value = (catalog.params.lora ?? []).map(({ file, strength }) => ({ file, strength }))
    q.value = ''
    onlySelected.value = false
  } else hidePreview()
})
function toggle(file) {
  if (selOf(file)) sel.value = sel.value.filter(s => s.file !== file)
  else if (!full.value) sel.value.push({ file, strength: strengthCtl.value.default })
}
async function remove(file, index) {
  toggle(file)
  hidePreview()
  await nextTick()
  const buttons = sidebar.value.querySelectorAll('.lora-remove')
  const target = buttons[Math.min(index, buttons.length - 1)] ?? sidebar.value
  target.focus()
}
function clearSelection() {
  sel.value = []
  hidePreview()
  sidebar.value?.focus()
}
function setStrength(file, values) {
  const entry = selOf(file)
  if (entry) entry.strength = values[0]
}
function onCoverError(file) { failed.value = new Set(failed.value).add(file) }
function clearFilters() { q.value = ''; onlySelected.value = false }
function close() { hidePreview(); emit('update:open', false) }
function confirm() {
  catalog.params.lora = sel.value.map(({ file, strength }) => ({ file, strength }))
  close()
}
/* Teleport outside the scroll area to avoid clipping.
   Ignore synthetic mouse events after touch so a tap cannot leave the preview open. */
const PREVIEW_MAX_W = 380
const PREVIEW_MAX_H = 460
const CURSOR_GAP = 16
const preview = ref(null) // { file, left, top }
let showTimer = 0
let lastMove = null
let lastTouchAt = 0
const isTouch = () => Date.now() - lastTouchAt < 800

function placePreview() {
  const { clientX: x, clientY: y } = lastMove
  const left = x + CURSOR_GAP + PREVIEW_MAX_W > innerWidth ? x - PREVIEW_MAX_W - CURSOR_GAP : x + CURSOR_GAP
  const top = Math.min(Math.max(y - PREVIEW_MAX_H / 2, 8), innerHeight - PREVIEW_MAX_H - 8)
  preview.value = { file: lastMove.file, left: Math.round(left), top: Math.round(top) }
}
function schedulePreview(file, event) {
  if (isTouch()) return
  clearTimeout(showTimer)
  lastMove = { clientX: event.clientX, clientY: event.clientY, file }
  if (preview.value?.file === file) return
  showTimer = setTimeout(() => {
    showTimer = 0
    if (lastMove) placePreview()
  }, 350)
}
function movePreview(e) {
  if (isTouch()) return
  lastMove = { clientX: e.clientX, clientY: e.clientY, file: lastMove?.file }
  if (preview.value && lastMove.file) placePreview()
}
function hidePreview() {
  clearTimeout(showTimer)
  showTimer = 0
  lastMove = null
  preview.value = null
}
function onTouchStart(event) {
  if (event.pointerType === 'mouse') return
  lastTouchAt = Date.now()
  hidePreview()
}
onBeforeUnmount(hidePreview)
</script>

<template>
  <Dialog :open="open" max-width="1160px" content-class="lora-picker" :close-label="t('viewer.close')" @update:open="emit('update:open', $event)">
    <template #title>
      <h2 class="lora-title">{{ t('lora.picker.title') }} <span class="lora-count" role="status" :aria-label="t('lora.picker.selected', { n: sel.length, max: LORA_MAX })">{{ sel.length }} / {{ LORA_MAX }}</span></h2>
    </template>
    <div class="lora-toolbar">
      <label class="lora-search">
        <span class="sr-only">{{ t('lora.picker.search') }}</span>
        <PhMagnifyingGlass :size="18" aria-hidden="true" />
        <input v-model="q" type="search" :placeholder="t('lora.picker.search')" translate="no" />
      </label>
      <button type="button" class="lora-filter" :aria-pressed="onlySelected" @click="onlySelected = !onlySelected">
        <PhCheck v-if="onlySelected" :size="14" aria-hidden="true" />{{ t('lora.picker.onlySelected') }}
      </button>
    </div>
    <div class="lora-layout">
      <section class="lora-catalog" tabindex="0" :aria-label="t('lora.picker.title')" @scroll.passive="hidePreview">
        <p v-if="!files.length" class="lora-empty">{{ t('lora.picker.empty') }}</p>
        <div v-else-if="!shown.length" class="lora-empty">
          <p>{{ t('lora.picker.noMatch') }}</p>
          <button type="button" class="lora-secondary" @click="clearFilters">{{ t('lora.picker.showAll') }}</button>
        </div>
        <div v-else class="lora-grid">
          <button v-for="file in shown" :key="file" type="button"
            :aria-label="labelOf(file)" :aria-pressed="!!selOf(file)" :disabled="!selOf(file) && full"
            :class="cn('lora-card', selOf(file) && 'is-selected')" @click="toggle(file)"
            @mouseenter="schedulePreview(file, $event)" @mousemove="movePreview" @mouseleave="hidePreview" @pointerdown="onTouchStart">
            <span class="lora-cover" aria-hidden="true">
              <img v-if="!failed.has(file)" :src="loraCoverUrl(file)" alt="" loading="lazy" @error="onCoverError(file)" />
              <PhImage v-else :size="28" />
              <span v-if="selOf(file)" class="lora-check"><PhCheck :size="14" weight="bold" /></span>
            </span>
            <span class="lora-name" translate="no"><bdi>{{ labelOf(file) }}</bdi></span>
          </button>
        </div>
      </section>
      <aside ref="sidebar" class="lora-mix" tabindex="-1" :aria-label="t('lora.picker.mixTitle')">
        <div class="lora-mix-heading">
          <h3>{{ t('lora.picker.mixTitle') }}</h3>
          <button type="button" class="lora-clear-desktop obs-tr min-h-8 rounded-md border border-destructive/60 bg-transparent px-2 py-1 text-[12px] text-destructive hover:enabled:bg-destructive/10 active:enabled:scale-95 disabled:cursor-not-allowed disabled:opacity-40 max-[760px]:min-h-10" :disabled="!sel.length" @click="clearSelection">{{ t('lora.picker.clearAll') }}</button>
        </div>
        <div class="lora-mix-list" @scroll.passive="hidePreview">
        <p v-if="!sel.length" class="lora-empty">{{ t('lora.picker.boardEmpty') }}</p>
        <div v-for="(s, index) in sel" :key="s.file" class="lora-mix-item rounded-md border border-control obs-inset px-3 pb-3 pt-2.5">
          <div class="lora-mix-title -mx-3 -mt-2.5 select-none px-3 pt-2.5"
            @mouseenter="schedulePreview(s.file, $event)" @mousemove="movePreview" @mouseleave="hidePreview" @pointerdown="onTouchStart">
            <h4 translate="no" :title="labelOf(s.file)"><bdi>{{ labelOf(s.file) }}</bdi></h4>
            <span class="shrink-0 font-mono text-[13px] font-semibold text-amber-bright tabular-nums" translate="no">{{ s.strength.toFixed(2) }}</span>
            <button
              type="button"
              :title="t('lora.remove', { name: labelOf(s.file) })"
              :aria-label="t('lora.remove', { name: labelOf(s.file) })"
              class="lora-remove obs-tr flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-control bg-plate text-ink-faint hover:border-destructive/60 hover:text-destructive active:scale-95"
              @click="remove(s.file, index)"
              @mouseenter="hidePreview"
              @mouseleave="schedulePreview(s.file, $event)"
            ><PhX class="h-3.5 w-3.5" aria-hidden="true" /></button>
          </div>
          <div class="lora-strength">
            <Slider :model-value="[s.strength]" :min="strengthCtl.min" :max="strengthCtl.max" :step="strengthCtl.step"
              :aria-label="t('lora.strength', { name: labelOf(s.file) })" :aria-valuetext="s.strength.toFixed(2)"
              @update:model-value="setStrength(s.file, $event)" />
          </div>
        </div>
        </div>
      </aside>
    </div>
    <footer class="lora-footer">
      <button type="button" class="lora-clear-mobile obs-tr min-h-8 rounded-md border border-destructive/60 bg-transparent px-2 py-1 text-[12px] text-destructive hover:enabled:bg-destructive/10 active:enabled:scale-95 disabled:cursor-not-allowed disabled:opacity-40 max-[760px]:min-h-10" :disabled="!sel.length" @click="clearSelection">{{ t('lora.picker.clearAll') }}</button>
      <p v-if="full" role="status">{{ t('lora.picker.limit') }}</p>
      <div><button type="button" class="lora-secondary" @click="close">{{ t('lora.picker.cancel') }}</button><button type="button" class="lora-confirm" @click="confirm">{{ t('lora.picker.confirm') }}</button></div>
    </footer>
    <Teleport to="body">
      <div
        v-if="open && preview"
        class="pointer-events-none fixed z-[60] overflow-hidden rounded-md border border-hairline bg-plate-bg p-1 shadow-[0_18px_48px_-12px_hsl(var(--dome)/.9)]"
        :style="{ left: `${preview.left}px`, top: `${preview.top}px` }"
      >
        <img
          v-if="!failed.has(preview.file)"
          :src="loraCoverUrl(preview.file)"
          :alt="t('lora.cover', { name: labelOf(preview.file) })"
          :style="{ maxWidth: `${PREVIEW_MAX_W}px`, maxHeight: `${PREVIEW_MAX_H}px` }"
          @error="onCoverError(preview.file)"
        />
        <PhImage v-else class="h-10 w-10 text-ink-faint" aria-hidden="true" />
      </div>
    </Teleport>
  </Dialog>
</template>

<style scoped>
:global(.lora-picker) { position: relative; display: flex; flex-direction: column; height: min(800px, calc(100dvh - 48px)); padding: 16px; overflow: hidden; }
.lora-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-height: 40px; flex-shrink: 0; padding-inline-end: 40px; color: hsl(var(--amber-bright)); font-size: 16px; font-weight: 700; letter-spacing: .12em; line-height: 1.5; }
.lora-count { padding: 2px 8px; border: 1px solid hsl(var(--amber) / .4); border-radius: 5px; background: hsl(var(--amber) / .1); color: hsl(var(--amber-bright)); font-size: 14px; font-weight: 700; letter-spacing: 0; font-variant-numeric: tabular-nums; }
.lora-toolbar { display: flex; flex-shrink: 0; gap: 8px; margin-block: 8px 12px; }
.lora-search { display: flex; align-items: center; gap: 10px; padding-inline: 12px; min-width: 0; flex: 1; border: 1px solid hsl(var(--control)); border-radius: 6px; background: hsl(var(--inset)); color: hsl(var(--muted-foreground)); }
.lora-search:focus-within { outline: 2px solid hsl(var(--amber)); outline-offset: 2px; }
.lora-search input { min-width: 0; width: 100%; height: 40px; background: transparent; color: hsl(var(--foreground)); font-size: 14px; outline: none; }
.lora-search input::placeholder { color: hsl(var(--muted-foreground)); }
.lora-filter,.lora-secondary,.lora-confirm { padding: 10px 16px; border: 1px solid hsl(var(--control)); border-radius: 5px; font-size: 13px; }
.lora-filter { display: flex; align-items: center; gap: 6px; }
.lora-filter[aria-pressed=true] { color: hsl(var(--amber-bright)); border-color: hsl(var(--amber)); }
.lora-layout { display: grid; grid-template-columns: minmax(0,1fr) 340px; flex: 1; min-height: 0; border-block: 1px solid hsl(var(--hairline)); }
.lora-catalog { padding: 12px 12px 12px 4px; min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.lora-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(152px,1fr)); gap: 12px; }
.lora-card { display: flex; flex-direction: column; min-width: 0; overflow: hidden; border: 1px solid hsl(var(--control)); border-radius: 6px; background: hsl(var(--inset)); text-align: start; }
.lora-card.is-selected { border-color: hsl(var(--amber)); }
@media (hover: hover) and (pointer: fine) {
  .lora-card:hover { border-color: hsl(var(--amber)); }
}
.lora-card.is-selected { background: hsl(var(--amber) / .06); }
.lora-card:disabled { opacity: .4; cursor: not-allowed; }
.lora-cover { position: relative; display: flex; align-items: center; justify-content: center; width: 100%; aspect-ratio: 3 / 4; flex-shrink: 0; overflow: hidden; background: hsl(var(--plate-bg)); color: hsl(var(--ink-faint)); }
.lora-cover img { width: 100%; height: 100%; object-fit: contain; }
.lora-check { position: absolute; top: 8px; inset-inline-end: 8px; display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: hsl(var(--amber)); color: hsl(var(--primary-foreground)); }
.lora-name { padding: 10px; min-height: 62px; font-size: 14px; line-height: 1.5; overflow-wrap: anywhere; }
.is-selected .lora-name { font-weight: 700; }
.lora-mix { display: flex; flex-direction: column; min-height: 0; padding: 12px 0 12px 12px; border-inline-start: 1px solid hsl(var(--hairline)); overflow: hidden; }
.lora-mix-heading { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; gap: 8px; margin-block-end: 8px; }
.lora-mix h3 { flex-shrink: 0; font-size: 14px; font-weight: 700; }
.lora-mix-list { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.lora-mix-list .lora-empty { padding: 12px 4px; text-align: start; }
.lora-mix-item { margin-block-end: 8px; }
.lora-mix-title { display: flex; align-items: center; gap: 12px; }
.lora-mix-title h4 { flex: 1; min-width: 0; font-size: 12.5px; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; }
.lora-strength { display: flex; align-items: center; height: 20px; margin-block-start: 8px; }
.lora-strength :deep([data-orientation=horizontal]) { min-width: 0; }
.lora-empty { padding: 32px 12px; color: hsl(var(--muted-foreground)); text-align: center; font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; }
.lora-empty button { margin-block-start: 16px; }
.lora-clear-mobile { display: none; }
.lora-footer { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; flex-wrap: wrap; gap: 12px; padding-block-start: 12px; }
.lora-footer p { font-size: 13px; color: hsl(var(--muted-foreground)); font-variant-numeric: tabular-nums; }
.lora-footer>div { display: flex; gap: 12px; margin-inline-start: auto; }
.lora-confirm { padding-inline: 24px; border-color: hsl(var(--amber)); color: hsl(var(--amber)); font-family: 'Chakra Petch', 'Taipei Sans TC', sans-serif; }
@media (hover: hover) {
  .lora-confirm:hover { background: hsl(var(--amber) / .1); color: hsl(var(--amber-bright)); }
  .lora-secondary:hover { background: hsl(var(--elevated)); }
}
@media (max-width: 760px) {
  :global(.lora-picker) { padding: 12px; height: calc(100dvh - 32px - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px)); }
  .lora-layout { display: flex; flex-direction: column; overflow: hidden; }
  .lora-catalog { flex: 1; min-height: 0; padding: 8px 4px; }
  .lora-grid { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; }
  .lora-mix { flex: 0 1 auto; max-height: 40%; padding: 8px 0 0; border-inline-start: 0; border-block-start: 1px solid hsl(var(--hairline)); }
  .lora-mix-heading { margin-block-end: 4px; }
  .lora-mix-list { min-height: 84px; max-height: 168px; }
  .lora-mix-list .lora-empty { display: flex; align-items: center; min-height: 84px; }
  .lora-mix-title h4 { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lora-search input { font-size: 16px; }
  .lora-filter { flex-shrink: 0; padding-inline: 8px; }
  .lora-clear-desktop { display: none; }
  .lora-clear-mobile { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .lora-footer p { order: -1; flex-basis: 100%; }
  .lora-footer { gap: 8px; padding-block-start: 8px; }
  .lora-footer>div { gap: 8px; }
}
@media (forced-colors: active) { .lora-search:focus-within { outline-color: Highlight; } }
</style>
