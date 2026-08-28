<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { clearHistory, history, timeOf } from '@/stores/history'
import { cn } from '@/lib/utils'
import { PhCaretDoubleRight, PhTrash, PhClockCounterClockwise } from '@phosphor-icons/vue'
import HistoryViewer from '@/components/obs/HistoryViewer.vue'
import ClearHistoryDialog from '@/components/obs/ClearHistoryDialog.vue'

const { t } = useI18n()

/* The stage is the point of this interface, but the two fixed columns, 364 and 264, never yield.
   At 840x500, a 1680 screen at 200% zoom, the stage is left with 212px and the viewfinder with 148px.
   So the rail collapses on its own once the stage would drop below 520px (364 + 264 + 520 = 1148).
   The collapse mechanism already existed; only the trigger was missing.

   It is a default, not a lock: the toggle still works in a narrow window, and returning to a wide one restores the choice made there. */
const NARROW = matchMedia('(max-width: 1147px)')
/* Collapsed by default: the stage is the point, and history is something you look back at rather than something that takes 264px from the first frame.
   The toggle still works and the narrow-window collapse is unchanged.
   The open prop exists for the /playground catalog only, which shows an expanded and a collapsed instance side by side.
   The workspace passes nothing and stays collapsed. */
const props = defineProps({ open: { type: Boolean, default: false } })
const closed = ref(!props.open)
let wideChoice = !props.open // the user's own choice in a wide window; collapsed by default
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

/** Whether the full-page clear-all confirmation is open. */
const confirming = ref(false)
const clearBtn = ref(null)
const headEl = ref(null)

/* At capacity, meaning history.limit from the backend, the header readout turns amber and gains an amber underline, so the colour signal is paired with a non-colour cue.
   The cap arrives as X-History-Limit on GET /v1/history.
   Until it has been asked for, whether it is full is unknown, so it counts as not full and the readout shows a dash: a guessed number would be a lie, the same rule as sizeOf returning null. */
const histFull = computed(() => history.limit !== null && history.entries.length >= history.limit)
const limitText = computed(() => history.limit ?? '—')

/* Collapsed is not a 44px empty column: a whole column holding one button is wasted real estate.
   The width goes to zero and the entry becomes a single button at the top right of the stage, inside the stage p-8 margin, so it never covers the viewfinder. - Collapsed, nothing says "history", so the icon is ClockCounterClockwise, the common history symbol, rather than text. - The unread badge is real state: how many arrived while collapsed.
   Expanding clears it. - The delivery animation flies a new output from the stage into that button, which then pulses amber.
   It plays only while collapsed: expanded, the user already saw the card appear, and repeating it would be performance rather than information. */
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

/* After a toggle, focus must land on whichever button takes over.
   Collapsing makes the whole panel inert and the header button disappears, so focus would drop to body.
   Opening gives focus to the header collapse control, collapsing gives it to the stage entry button.
   The automatic collapse on a narrowing window does not come through here, because focus was not inside the rail then anyway. */
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

/* After a confirmed clear the clear button is disabled, because the rail is empty, so focus moves to the top of the rail instead of evaporating.
   Cancelling returns it to the clear button. */
async function onConfirmClear() {
  confirming.value = false
  await clearHistory()
  nextTick(() => headEl.value?.focus())
}
function onCancelClear() {
  confirming.value = false
  nextTick(() => clearBtn.value?.focus())
}
</script>

<template>
  <!-- The toggle animates exactly one property: the column width.
       The panel is a fixed 264px anchored to the right edge and never moves; the overflow:hidden layer around it does the clipping, so widening the column uncovers the panel from right to left.
       The stage edge sweeps across and reveals it with no content shift and no reflow.

       Animating the width and a panel translateX together would require the two curves to agree on every frame.
       If one of them does not move, and in practice the panel snapped into place while only the width animated, it reads as the rail appearing instantly and then the left edge racing into position.
       With one property that cannot happen.
       Opening takes 220ms and closing 180ms. -->
  <aside
    :aria-label="t('history.title')"
    :class="cn('rail relative flex min-h-0 flex-col', closed ? 'rail-closed w-0' : 'w-[264px]')"
  >
    <!-- Collapsed entry, at the top right of the stage. h-8 w-8 matches every icon button inside the rail. -->
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

    <!-- The clipping layer follows the column width and does the revealing.
         The entry button is a direct child of the aside rather than of this layer, so a zero width does not clip it away too. -->
    <div class="absolute inset-0 overflow-hidden">
    <div
      class="obs-panel absolute inset-y-0 right-0 flex w-[264px] flex-col overflow-hidden border-l border-hairline"
      :inert="closed || undefined"
    >
      <!-- The header is the collapse control.
           A separate sidebar icon button meant nothing on its own and added one more size to the set.
           The whole title row is pressable, and the guillemet on the left implies collapsing to the right; hovering pushes it 2px right to finish the sentence.

           The top right corner deliberately holds only the readout, itself part of the collapse control, because that corner is exactly where the collapsed entry button sits: the two centres coincide.
           Wherever the user just pressed to open, the second press must be "put it back", never something destructive, which is why clear-all lives at the bottom of the rail. -->
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
          <!-- The N/LIMIT readout lives in the header, the only chrome left in the rail and visible throughout scrolling -->
          <span
            class="ml-auto font-mono text-[11px] tracking-[.04em] tabular-nums"
            :class="histFull && 'underline decoration-amber decoration-2 underline-offset-4'"
            :title="histFull ? t('history.fullTip', { limit: limitText }) : t('history.countTip', { count: history.entries.length, limit: limitText })"
            translate="no"
          ><span :class="histFull ? 'text-amber-bright' : 'text-foreground'">{{ history.entries.length }}</span><span :class="histFull ? 'text-amber' : 'text-ink-faint'">/{{ limitText }}</span></span>
        </button>
      </div>

      <!-- Empty state.
           A blank 264px column is not clean, it is unexplained.
           One sentence says what will grow here, with no panel, no border and no icon: a place with no evidence does not need decoration to fill it. -->
      <p
        v-if="!history.entries.length"
        class="flex-1 px-4 pt-6 text-center font-sans text-[12px] leading-[1.9] text-ink-faint"
      >{{ t('history.empty') }}</p>

      <!-- The resting frame.
           A single 1px --control line over the dark ambient backdrop was barely readable, which turned it into "a frame only on hover".
           The fix is not amber at rest, because amber is instrumentation rather than a permanent outline, but the same language as the stage viewfinder: an outer seat, a 3px mat and an inner hairline.
           Two lines build a real picture frame that is visible at rest, and hover still only turns the outer line amber. -->
      <TransitionGroup v-else tag="div" name="hist" class="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
        <button
          v-for="(entry, i) in history.entries"
          :key="entry.promptId"
          type="button"
          class="obs-tr obs-elevated flex-none cursor-pointer rounded-[3px] border border-control p-[3px] hover:border-amber"
          :aria-label="t('history.viewAt', { n: i + 1, total: history.entries.length, time: timeOf(entry.finishedAt) })"
          @click="openViewer(i, $event)"
        >
          <!-- The backend has no thumbnails and returns the full image, so the box is a fixed square and loads only when scrolled to.
               The ambient backdrop is the same image scaled to fill, heavily blurred and darkened, covering the gaps beside a portrait or above a landscape image.
               It is decoration only and aria-hidden; the evidence itself stays the real object-contain image, uncropped.
               Darkening and desaturating keep the rail colours from outranking the amber instrumentation. -->
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
      </TransitionGroup>

      <!-- Clear all, pinned to the bottom of the rail and never scrolled.
           It is in the same place with 3 images as with 50.
           It cannot go in the top right of the title row: that corner is where the collapsed entry button sits, and the second press wherever the user just opened must be "put it back", not something destructive.
           With nothing to clear, the whole row does not exist.

           It is an outline button rather than a full-width red bar.
           A solid red field would swallow the hairline next to it, and an action that should rarely be pressed does not need the heaviest visual in the column.
           At rest it is red text and a red border, which is enough to find; the fill is left to hover.
           The border-t above it is not optional: a scrolling list sits above, and on whitespace alone the cards would slide under the button and look like they were burrowing into it. -->
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
/* The toggle: this is the only thing that animates.
   Closing takes 180ms. */
.rail { transition: width .22s var(--ease-fluid); }
.rail-closed { transition-duration: .18s; }

/* The entry button appears only once the panel is out of the way, after a .1s delay, and leaves immediately with no delay and a shorter duration.
   scale(.9) rather than scale(0): nothing in the real world grows out of nothing. */
.entry {
  opacity: 1; transform: scale(1);
  transition: opacity .16s var(--ease-fluid) .1s, transform .16s var(--ease-fluid) .1s,
              border-color .16s var(--ease-fluid), color .16s var(--ease-fluid);
}
.entry:active { transform: scale(.95); transition-duration: .1s; transition-delay: 0s; }
.entry-off { opacity: 0; transform: scale(.9); pointer-events: none; transition-delay: 0s; transition-duration: .12s; }

/* The guillemet slides 2px right on hover, which says "this collapses to the right" without using words */
.head-caret { transition: transform .16s var(--ease-fluid); }
.head-btn:hover .head-caret { transform: translateX(2px); }

/* A new card floats in from 6px above, and its siblings slide into place through FLIP, overriding the .2s transform of obs-tr */
.hist-enter-active { transition: opacity .3s var(--ease-fluid), transform .3s var(--ease-fluid); }
.hist-enter-from   { opacity: 0; transform: translateY(-6px); }
.hist-move         { transition: transform .3s var(--ease-fluid); }
/* Removal, from clear-all, only fades: a FLIP group move while everything leaves at once is noise */
.hist-leave-active { transition: opacity .12s ease-out; }
.hist-leave-to     { opacity: 0; }

/* Delivery: a new output flies from the stage into the entry button and disappears once it coincides with it, animating transform and opacity only.
   The end size of 32px is the button's 32px, so it is caught by the button rather than landing beside it. */
.hist-drop {
  right: 12px; top: 12px;
  /* The host aside is 0 wide once collapsed, and the preflight img{max-width:100%} would resolve to 0, so it is released here */
  width: 32px; height: 32px; max-width: none;
  /* The image is still uncropped, the same language as the history cards: contain over the image-well background */
  object-fit: contain; background: hsl(var(--plate-bg));
  border-radius: 3px; border: 1px solid hsl(var(--amber));
  animation: histDrop .42s var(--ease-fluid) both;
}
/* Opacity holds until 82% of the flight.
   ease-fluid is very fast at the start, so fading from 18% onward would leave four fifths of the flight invisible,
   which is the same as having no animation at all. */
@keyframes histDrop {
  0%   { transform: translate(-150px, 140px) scale(2.8); opacity: 0; }
  15%  { opacity: 1; }
  82%  { opacity: 1; }
  100% { transform: translate(0, 0) scale(1); opacity: 0; }
}
/* Landing: at the moment of the catch, the button expands an amber ring.
   The delay lines up with where the delivery lands. */
.hist-land { animation: histLand .46s var(--ease-fluid) .36s both; }
@keyframes histLand {
  0%   { box-shadow: 0 0 0 0 hsl(var(--amber) / .5); }
  100% { box-shadow: 0 0 0 12px hsl(var(--amber) / 0); }
}
/* Reduced motion: neither the delivery nor the landing plays, and the unread badge stays.
   The state does not disappear, it just stops performing. */
@media (prefers-reduced-motion: reduce) {
  .hist-drop, .hist-land { animation: none; }
}
</style>
