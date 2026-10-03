<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { clearHistory, deleteHistoryEntry, history, timeOf } from '@/stores/history'
import { cn } from '@/lib/utils'
import { PhCaretDoubleRight, PhTrash, PhClockCounterClockwise } from '@phosphor-icons/vue'
import HistoryViewer from '@/components/obs/HistoryViewer.vue'
import ClearHistoryDialog from '@/components/obs/ClearHistoryDialog.vue'

const { t } = useI18n()

/* Collapse below 364px parameters + 264px history + 520px stage.
   Returning to a wide window restores its previous choice; manual toggling remains available. */
const NARROW = matchMedia('(max-width: 1147px)')
const props = defineProps({ open: { type: Boolean, default: false } })
const closed = ref(!props.open)
let wideChoice = !props.open
const onNarrow = (e) => {
  if (e.matches) {
    wideChoice = closed.value
    closed.value = true
  } else {
    closed.value = wideChoice
  }
}
onMounted(() => NARROW.addEventListener('change', onNarrow))
onBeforeUnmount(() => {
  NARROW.removeEventListener('change', onNarrow)
  clearTimeout(dropTimer)
})
/** Index of the history entry the viewer is showing; null means closed. */
const viewIndex = ref(null)
/** The card that opened the viewer; focus returns to it on close. */
let triggerEl = null

const confirming = ref(false)
const clearBtn = ref(null)
const headEl = ref(null)

const histFull = computed(() => history.limit !== null && history.entries.length >= history.limit)
const limitText = computed(() => history.limit ?? '—')

// Count arrivals while collapsed; opening the rail clears the badge.
const unread = ref(0)
/** URL of the image being delivered.
 * Non-empty means the animation is running, and it also drives the landing pulse on the button. */
const dropping = ref('')
let dropTimer = 0
const REDUCE = matchMedia('(prefers-reduced-motion: reduce)')

watch(
  () => history.entries[0]?.promptId,
  (id, prev) => {
    // prev === undefined is the first history load, not a newly arrived image
    if (!closed.value || !id || prev === undefined) return
    unread.value += 1
    if (REDUCE.matches) return
    dropping.value = history.entries[0]?.images?.[0] || ''
    clearTimeout(dropTimer)
    dropTimer = setTimeout(() => { dropping.value = '' }, 900)
  },
)
watch(closed, (c) => { if (!c) unread.value = 0 })

// Transfer focus to the visible toggle when the previous one becomes inaccessible.
const entryBtn = ref(null)
const headBtn = ref(null)
function openRail() {
  closed.value = false
  nextTick(() => headBtn.value?.focus())
}
function collapseRail() {
  closed.value = true
  nextTick(() => entryBtn.value?.focus())
}

function openViewer(i, e) {
  triggerEl = e.currentTarget
  viewIndex.value = i
}
function closeViewer() {
  viewIndex.value = null
  nextTick(() => triggerEl?.focus())
}

// Clearing removes the clear button, so return focus to the persistent header.
async function onConfirmClear() {
  confirming.value = false
  await clearHistory()
  nextTick(() => headEl.value?.focus())
}
function onCancelClear() {
  confirming.value = false
  nextTick(() => clearBtn.value?.focus())
}

/* Width: one column by default, so each thumbnail is as large as the rail allows.
   Dragging the left edge widens it; from 1.5 times the default the grid switches to two columns.
   The stage keeps its 520px minimum, and the chosen width is remembered per browser. */
const RAIL_MIN = 264
const RAIL_MAX = 560
const STAGE_MIN = 364 + 520 // the parameter column plus the smallest useful stage
const WIDTH_KEY = 'comfy.historyRailWidth'
const maxWidth = () => Math.max(RAIL_MIN, Math.min(RAIL_MAX, window.innerWidth - STAGE_MIN))
const clampWidth = (w) => Math.round(Math.min(Math.max(w, RAIL_MIN), maxWidth()))
const readWidth = () => {
  try { return Number(localStorage.getItem(WIDTH_KEY)) || RAIL_MIN } catch { return RAIL_MIN }
}
const railWidth = ref(clampWidth(readWidth()))
const TWO_COLUMNS_AT = RAIL_MIN * 1.5 // 396px
const columns = computed(() => (railWidth.value >= TWO_COLUMNS_AT ? 2 : 1))
const resizing = ref(false)
function saveWidth() {
  try { localStorage.setItem(WIDTH_KEY, String(railWidth.value)) } catch { /* storage blocked: width lasts this visit */ }
}
let dragFrom = null
function onResizeDown(e) {
  if (e.button !== 0) return
  e.currentTarget.setPointerCapture(e.pointerId)
  dragFrom = { x: e.clientX, w: railWidth.value }
  resizing.value = true
}
function onResizeMove(e) {
  if (!dragFrom) return
  railWidth.value = clampWidth(dragFrom.w + dragFrom.x - e.clientX) // dragging left widens
}
function onResizeUp() {
  if (!dragFrom) return
  dragFrom = null
  resizing.value = false
  saveWidth()
}
const RESIZE_STEP = 24
const RESIZE_KEYS = {
  ArrowLeft: (w) => w + RESIZE_STEP,
  ArrowRight: (w) => w - RESIZE_STEP,
  Home: () => RAIL_MIN,
  End: () => RAIL_MAX,
}
function onResizeKey(e) {
  const next = RESIZE_KEYS[e.key]
  if (!next) return
  e.preventDefault()
  railWidth.value = clampWidth(next(railWidth.value))
  saveWidth()
}
// Double-click returns to the single-column default
function resetWidth() {
  railWidth.value = RAIL_MIN
  saveWidth()
}
const onWinResize = () => { railWidth.value = clampWidth(railWidth.value) }
onMounted(() => window.addEventListener('resize', onWinResize))
onBeforeUnmount(() => window.removeEventListener('resize', onWinResize))

// Single delete: confirm first, then hand focus to the card that slid into its place
const removing = ref(null) // { promptId, index }
const cardList = ref(null)
function askRemove(entry, index) {
  removing.value = { promptId: entry.promptId, index }
}
async function onConfirmRemove() {
  const { promptId, index } = removing.value
  removing.value = null
  const ok = await deleteHistoryEntry(promptId)
  await nextTick()
  // Look the card up by id: the deleted one is still in the DOM while it fades out
  const next = history.entries[ok ? Math.min(index, history.entries.length - 1) : index]
  const card = next && cardList.value?.$el?.querySelector(`[data-prompt-id="${CSS.escape(next.promptId)}"] .hist-open`)
  ;(card ?? headEl.value)?.focus()
}
function onCancelRemove() {
  const { index } = removing.value
  removing.value = null
  nextTick(() => cardList.value?.$el?.querySelectorAll('.hist-del')[index]?.focus())
}
</script>

<template>
  <!-- Animate the clipping width around a fixed-width panel to keep card contents from reflowing. -->
  <aside
    :aria-label="t('history.title')"
    :class="cn('rail relative flex min-h-0 flex-col', closed && 'rail-closed', resizing && 'rail-resizing')"
    :style="{ width: closed ? '0px' : `${railWidth}px` }"
  >
    <img
      v-if="dropping && closed"
      :src="dropping"
      class="hist-drop pointer-events-none absolute z-30"
      alt=""
      aria-hidden="true"
    />
    <button
      type="button"
      ref="entryBtn"
      :inert="!closed"
      :title="t('history.title')"
      :aria-label="unread ? t('history.expandUnread', { n: unread }) : t('history.expand')"
      :class="cn(
        'entry obs-elevated absolute right-3 top-3 z-30 grid h-8 w-8 cursor-pointer place-items-center rounded-sm border border-control text-muted-foreground hover:border-amber hover:text-amber',
        !closed && 'entry-off',
        dropping && closed && 'hist-land',
      )"
      @click="openRail"
    >
      <PhClockCounterClockwise class="h-4 w-4" aria-hidden="true" />
      <span
        v-if="unread"
        class="absolute -right-1.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-amber px-1 font-mono text-[11px] font-bold leading-none text-dome tabular-nums"
        translate="no"
      >{{ unread > 9 ? '9+' : unread }}</span>
    </button>

    <!-- Keep the entry button outside this layer so it survives clipping to zero width. -->
    <div class="absolute inset-0 overflow-hidden">
    <div
      class="rail-panel obs-panel absolute inset-y-0 right-0 flex flex-col overflow-hidden border-l border-hairline"
      :style="{ width: `${railWidth}px` }"
      :inert="closed || undefined"
    >
      <!-- Resize grip on the left edge: a thin hit strip whose line lights up on hover, focus or drag -->
      <div
        class="rail-grip absolute inset-y-0 left-0 z-20 w-2 cursor-col-resize touch-none"
        :class="resizing && 'is-active'"
        role="separator"
        aria-orientation="vertical"
        tabindex="0"
        :aria-label="t('history.resize')"
        :title="t('history.resize')"
        :aria-valuemin="RAIL_MIN"
        :aria-valuemax="RAIL_MAX"
        :aria-valuenow="railWidth"
        @pointerdown="onResizeDown"
        @pointermove="onResizeMove"
        @pointerup="onResizeUp"
        @pointercancel="onResizeUp"
        @lostpointercapture="onResizeUp"
        @dblclick="resetWidth"
        @keydown="onResizeKey"
      />
      <div ref="headEl" tabindex="-1" class="flex flex-none items-center border-b border-hairline px-2 py-3">
        <button
          type="button"
          class="head-btn obs-tr -my-1 flex w-full min-w-0 cursor-pointer items-center gap-2 rounded-sm px-1 py-1 text-left hover:bg-elevated"
          ref="headBtn"
          :aria-label="t('history.collapse')"
          @click="collapseRail"
        >
          <PhCaretDoubleRight class="head-caret h-3.5 w-3.5 flex-none text-ink-faint" aria-hidden="true" />
          <span class="whitespace-nowrap font-sans text-[13px] font-bold tracking-[.2em] text-muted-foreground">{{ t('history.title') }}</span>
          <span
            class="ml-auto font-mono text-[11px] tracking-[.04em] tabular-nums"
            :class="histFull && 'underline decoration-amber decoration-2 underline-offset-4'"
            :title="histFull ? t('history.fullTip', { limit: limitText }) : t('history.countTip', { count: history.entries.length, limit: limitText })"
            translate="no"
          ><span :class="histFull ? 'text-amber-bright' : 'text-foreground'">{{ history.entries.length }}</span><span :class="histFull ? 'text-amber' : 'text-ink-faint'">/{{ limitText }}</span></span>
        </button>
      </div>

      <p
        v-if="!history.entries.length"
        class="flex-1 px-4 pt-6 text-center font-sans text-[12px] leading-[1.9] text-ink-faint"
      >{{ t('history.empty') }}</p>

      <!-- One column, or two once the rail is 1.5 times its default width. The stable gutter keeps the
           column width from jumping when the scrollbar appears. -->
      <TransitionGroup
        v-else
        ref="cardList"
        tag="div"
        name="hist"
        class="hist-grid grid flex-1 auto-rows-min content-start overflow-y-auto p-3"
        :class="columns === 2 ? 'gap-2' : 'gap-3'"
        :style="{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }"
      >
        <div v-for="(entry, i) in history.entries" :key="entry.promptId" class="group relative" :data-prompt-id="entry.promptId">
          <button
            type="button"
            class="hist-open obs-tr obs-elevated block w-full cursor-pointer rounded-[3px] border border-control p-[3px] hover:border-amber"
            :aria-label="t('history.viewAt', { n: i + 1, total: history.entries.length, time: timeOf(entry.finishedAt) })"
            @click="openViewer(i, $event)"
          >
            <!-- These URLs serve full-size images, so defer offscreen loads. -->
            <div class="relative aspect-square w-full overflow-hidden border border-hairline bg-plate-bg">
              <img
                :src="entry.images[0]"
                loading="lazy"
                decoding="async"
                alt=""
                aria-hidden="true"
                class="pointer-events-none absolute inset-0 h-full w-full scale-125 object-cover blur-[16px] brightness-[.45] saturate-[.8]"
              />
              <img
                :src="entry.images[0]"
                class="relative h-full w-full object-contain"
                loading="lazy"
                decoding="async"
                alt=""
              />
            </div>
          </button>
          <!-- A sibling, not a child: a button cannot hold another button. Revealed on hover or focus, always shown without hover. -->
          <button
            type="button"
            class="hist-del obs-ghost obs-tr absolute right-1.5 top-1.5 grid h-7 w-7 cursor-pointer place-items-center rounded-sm border border-hairline text-muted-foreground opacity-0 hover:border-destructive/70 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100 active:scale-95 [@media(hover:none)]:opacity-100"
            :aria-label="t('history.remove.aria', { n: i + 1, time: timeOf(entry.finishedAt) })"
            :title="t('history.remove.title')"
            @click="askRemove(entry, i)"
          ><PhTrash class="h-3.5 w-3.5" aria-hidden="true" /></button>
        </div>
      </TransitionGroup>

      <!-- Keep clear-all away from the entry toggle so a second click after opening cannot hit it. -->
      <div v-if="history.entries.length" class="flex-none border-t border-hairline p-3">
        <button
          ref="clearBtn"
          type="button"
          class="obs-tr flex h-8 w-full cursor-pointer items-center justify-center gap-2 rounded-sm border border-destructive/60 font-sans text-[12px] font-bold tracking-[.14em] text-destructive hover:border-destructive hover:bg-destructive/15"
          @click="confirming = true"
        >
          <PhTrash class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t('history.clearAll') }}
        </button>
      </div>

    </div>
    </div>

    <Transition name="viewer">
      <HistoryViewer v-if="viewIndex !== null" :entries="history.entries" :start-index="viewIndex" @close="closeViewer" />
    </Transition>
    <Transition name="chd">
      <ClearHistoryDialog v-if="removing" :count="1" single @confirm="onConfirmRemove" @cancel="onCancelRemove" />
    </Transition>
    <Transition name="chd">
      <ClearHistoryDialog
        v-if="confirming"
        :count="history.entries.length"
        @confirm="onConfirmClear"
        @cancel="onCancelClear"
      />
    </Transition>
  </aside>
</template>

<style scoped>
.rail { transition: width .22s var(--ease-fluid); }
.rail-closed { transition-duration: .18s; }
/* Follow the pointer directly while dragging; the eased width is only for opening and closing */
.rail-resizing { transition: none; user-select: none; }

.hist-grid { scrollbar-gutter: stable; }

.rail-grip::after {
  content: ''; position: absolute; inset-block: 0; left: -1px; width: 2px;
  background: hsl(var(--amber)); opacity: 0; transition: opacity .16s var(--ease-fluid);
}
.rail-grip:focus-visible { outline: none; }
.rail-grip:focus-visible::after,
.rail-grip.is-active::after { opacity: 1; }
@media (hover: hover) {
  .rail-grip:hover::after { opacity: .6; }
}

/* Isolate the fixed-width card layout from the animated column width. */
.rail-panel { contain: layout paint; }

/* Delay entry until the panel has moved clear; hide immediately when reopening. */
.entry {
  opacity: 1; transform: scale(1);
  transition: opacity .16s var(--ease-fluid) .1s, transform .16s var(--ease-fluid) .1s,
              border-color .16s var(--ease-fluid), color .16s var(--ease-fluid);
}
.entry:active { transform: scale(.95); transition-duration: .1s; transition-delay: 0s; }
.entry-off { opacity: 0; transform: scale(.9); pointer-events: none; transition-delay: 0s; transition-duration: .12s; }

.head-caret { transition: transform .16s var(--ease-fluid); }
@media (hover: hover) {
  .head-btn:hover .head-caret { transform: translateX(2px); }
}

.hist-enter-active { transition: opacity .3s var(--ease-fluid), transform .3s var(--ease-fluid); }
.hist-enter-from   { opacity: 0; transform: translateY(-6px); }
.hist-move         { transition: transform .3s var(--ease-fluid); }
.hist-leave-active { transition: opacity .12s ease-out; }
.hist-leave-to     { opacity: 0; }

/* Match the entry button's position and dimensions at the end of delivery. */
.hist-drop {
  right: 12px; top: 12px;
  /* The host aside is 0 wide once collapsed, and the preflight img{max-width:100%} would resolve to 0, so it is released here */
  width: 32px; height: 32px; max-width: none;
  object-fit: contain; background: hsl(var(--plate-bg));
  border-radius: 3px; border: 1px solid hsl(var(--amber));
  animation: histDrop .42s var(--ease-fluid) both;
}
/* Hold opacity until near landing so the delivery remains visible through the easing tail. */
@keyframes histDrop {
  0%   { transform: translate(-150px, 140px) scale(2.8); opacity: 0; }
  15%  { opacity: 1; }
  82%  { opacity: 1; }
  100% { transform: translate(0, 0) scale(1); opacity: 0; }
}
/* Synchronize the ring with the delivery's landing. */
.hist-land { animation: histLand .46s var(--ease-fluid) .36s both; }
@keyframes histLand {
  0%   { box-shadow: 0 0 0 0 hsl(var(--amber) / .5); }
  100% { box-shadow: 0 0 0 12px hsl(var(--amber) / 0); }
}
@media (prefers-reduced-motion: reduce) {
  .hist-drop, .hist-land { animation: none; }
}
</style>
