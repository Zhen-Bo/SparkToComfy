<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  modelValue: { type: String, default: '' },
  class: { type: String, default: '' },
  // Tag-based prompts opt out of spellcheck; sentence fields can enable it.
  spellcheck: { type: Boolean, default: false },
  /* A share of the scroll area's common free-height pool: 0 keeps the rows height, 1 takes it all.
     Minimum rows and long content may make the fields taller than their shares. */
  fill: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue'])
// Forward field attributes to the textarea instead of the wrapper needed for its fade overlay.
defineOptions({ inheritAttrs: false })

/* Treat rows as a minimum and cap growth against the enclosing scroll area, not the viewport,
   so long prompts leave room for other controls. The fill allocation can raise this cap. */
const CAP_PX = 250 // roughly 12 lines
const CAP_RATIO = 0.3 // largest share of the outer scroll area it may take

const el = ref(null)
const clipped = ref(false)
let floor = 0 // height implied by rows, measured once
// scrollHeight excludes borders, but the assigned border-box height must include them.
let borders = 0

function measureSlack(port) {
  if (props.fill <= 0 || !port) return 0
  const last = port.lastElementChild
  if (!last) return 0
  /* Every fill field must measure the same pool. Temporarily removing all of them
     prevents their current heights and callback order from changing each other's shares. */
  const peers = [...port.querySelectorAll('textarea[data-fill-share]')]
  const peerHeights = peers.map((peer) => peer.style.height)
  peers.forEach((peer) => { peer.style.height = '0px' })
  const padB = parseFloat(getComputedStyle(port).paddingBottom) || 0
  const pool = Math.max(0, port.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom - padB)
  peers.forEach((peer, i) => {
    if (peer !== el.value) peer.style.height = peerHeights[i]
  })
  return pool * props.fill
}

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
  // scrollHeight cannot measure unused space when content is shorter than its container.
  const slack = measureSlack(port)
  // The share replaces the minimum when larger; adding it to floor would count the field twice.
  const lo = Math.max(floor, slack)
  const hi = Math.max(cap, slack)
  t.style.height = Math.max(lo, Math.min(hi, t.scrollHeight + borders)) + 'px'
  clipped.value = t.scrollHeight - t.scrollTop - t.clientHeight > 1
}

let ro
onMounted(() => {
  // Refit when wrapping width or the enclosing height changes.
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
      :data-fill-share="props.fill > 0 || undefined"
      :spellcheck="props.spellcheck"
      :class="cn(
        'block max-h-[60vh] w-full resize-none overflow-y-auto rounded-md border border-control obs-inset px-3 py-2 font-mono text-xs leading-relaxed text-foreground obs-tr placeholder:text-ink-faint focus-visible:border-amber disabled:cursor-not-allowed disabled:opacity-50',
        props.class,
      )"
      :value="modelValue"
      @input="emit('update:modelValue', $event.target.value)"
      @scroll="clipped = $event.target.scrollHeight - $event.target.scrollTop - $event.target.clientHeight > 1"
    />
    <div
      v-show="clipped"
      class="pointer-events-none absolute inset-x-px bottom-px h-3 rounded-b-md"
      style="background: linear-gradient(hsl(var(--inset) / 0), hsl(var(--inset)))"
      aria-hidden="true"
    />
  </div>
</template>
