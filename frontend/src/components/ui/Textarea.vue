<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  modelValue: { type: String, default: '' },
  class: { type: String, default: '' },
  // Prompts are mostly tags, where the red squiggles are only noise.
  // A field holding real sentences turns this on at the call site.
  spellcheck: { type: Boolean, default: false },
  /* Take the leftover height of the scroll area.
     Only one field per scroll area may turn this on, or two of them would fight over it and oscillate.
     It exists to remove the roughly 100px empty band above the generate row: better to give those lines to the field that needs them than to leave an empty plate.
     It cannot chase itself, because slack is measured after this field's own height is zeroed, so the leftover it sees excludes it (see fit). */
  fill: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
// The root is a wrapper, because <textarea> takes no pseudo-elements and the fade must be a real div.
// rows, maxlength and aria-* are therefore forwarded to the textarea by hand instead of landing on the wrapper.
defineOptions({ inheritAttrs: false })

/* The field grows with its content, and the outer panel does the scrolling.
   The panel scrolls anyway, so a second scrollbar inside a five-row window is not needed:
   with fixed rows, 285 characters, a fifth of the cap, already forces the user to drag the UA resize handle to see what they have written.
   rows therefore means "keep at least this many lines"; the declaration file is still the source of the layout contract.

   The ceiling is computed, and it measures the outer scroll area rather than the window.
   A plain vh unit works backwards: the taller the window, the more the field takes.
   At a 1310px window 40vh is 522px, 49% of the scroll area, which pushes the whole size section below the fold;
   at a 700px window a fixed 250px is 54%.
   min(250px, 30% of the scroll area) crowds nobody out at either end.
   Pure CSS cannot do this: container-type:size would make position:fixed descendants resolve against it and break the drag ghost in LoraField.
   Beyond the ceiling it scrolls internally, with the bottom fade and the counter as the hint,
   and a real rewrite belongs in the expand editor on the title row. */
const CAP_PX = 250 // roughly 12 lines
const CAP_RATIO = 0.3 // largest share of the outer scroll area it may take

const el = ref(null)
const clipped = ref(false)
let floor = 0 // height implied by rows, measured once
// box-sizing is border-box but scrollHeight excludes the border; without these 2px it is always slightly short
let borders = 0

const fit = () => {
  const t = el.value
  if (!t) return
  if (!floor) {
    const cs = getComputedStyle(t)
    borders = parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth)
    floor = t.clientHeight + borders // only measurable once it is first visible
  }
  // Where no scroll area is marked, in /playground and the expand dialog, there is no cap and the local max-h takes over.
  const port = t.closest('[data-fieldport]')
  const cap = port ? Math.min(CAP_PX, port.clientHeight * CAP_RATIO) : Infinity
  t.style.height = '0px'
  /* Measured after zeroing, so the leftover excludes this field and slack is a stable value that cannot oscillate through fit, grow, fit again.
     scrollHeight will not do: with content shorter than the container it equals clientHeight and never shows the leftover.
     So it measures the scroll area bottom minus the last section bottom, less the scroll area's own bottom padding, which is layout rather than empty space. */
  let slack = 0
  if (props.fill && port) {
    const last = port.lastElementChild
    if (last) {
      const padB = parseFloat(getComputedStyle(port).paddingBottom) || 0
      slack = Math.max(0, port.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom - padB)
    }
  }
  /* slack is the entire height available to this field once zeroed, not an extra increment: adding it to floor would count this field twice.
     With fill it raises both the floor, so an empty field still fills, and the ceiling, so long content can reach at least that far. */
  const lo = Math.max(floor, slack)
  const hi = Math.max(cap, slack)
  t.style.height = Math.max(lo, Math.min(hi, t.scrollHeight + borders)) + 'px'
  clipped.value = t.scrollHeight - t.scrollTop - t.clientHeight > 1
}

let ro
onMounted(() => {
  // A width change rewraps and a scroll-area height change moves the ceiling.
  // It observes the wrapper rather than the textarea, so changing its own height does not retrigger itself in a loop.
  ro = new ResizeObserver(fit)
  ro.observe(el.value.parentElement)
  const port = el.value.closest('[data-fieldport]')
  if (port) ro.observe(port)
  fit()
})
onBeforeUnmount(() => ro?.disconnect())
watch(() => props.modelValue, () => nextTick(fit))
</script>

<template>
  <div class="relative">
    <textarea
      ref="el"
      v-bind="$attrs"
      :spellcheck="props.spellcheck"
      :class="cn(
        'block max-h-[60vh] w-full resize-none overflow-y-auto rounded-md border border-control obs-inset px-3 py-2 font-mono text-xs leading-relaxed text-foreground obs-tr placeholder:text-ink-faint focus-visible:border-amber disabled:cursor-not-allowed disabled:opacity-50',
        props.class,
      )"
      :value="modelValue"
      @input="emit('update:modelValue', $event.target.value)"
      @scroll="clipped = $event.target.scrollHeight - $event.target.scrollTop - $event.target.clientHeight > 1"
    />
    <!-- inset-x-px and bottom-px stop just inside the 1px border rather than covering it -->
    <div
      v-show="clipped"
      class="pointer-events-none absolute inset-x-px bottom-px h-3 rounded-b-md"
      style="background: linear-gradient(hsl(var(--inset) / 0), hsl(var(--inset)))"
      aria-hidden="true"
    />
  </div>
</template>
