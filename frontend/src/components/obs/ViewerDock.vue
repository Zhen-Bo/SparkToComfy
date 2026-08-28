<script setup>
/* The bottom navigation dock sits below the viewport edge and rises when the pointer enters the bottom hot zone or Tab reaches one of its buttons.
   It rises immediately, with no delay timer.
   The hot zone is also part of "click outside the image to close", so clicks on the dock itself stop propagation.
   The dock stays an 88% ghost to hold the readability floor over bright images.

   Touch devices have no hover, so there the dock stays out.
   While risen it overlays the image, the usual image-viewer behaviour, so it takes no layout space and the fit maths never involves it. */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PhCaretLeft, PhCaretRight } from '@phosphor-icons/vue'

const { t } = useI18n()

defineProps({
  index: { type: Number, required: true },
  total: { type: Number, required: true },
  time: { type: String, required: true },
})
const emit = defineEmits(['go', 'close'])

const hoverCapable = typeof matchMedia !== 'undefined' && matchMedia('(hover: hover)').matches
const up = ref(!hoverCapable)
const el = ref(null)

function enter() {
  if (hoverCapable) up.value = true
}
function leave() {
  if (hoverCapable && !el.value?.contains(document.activeElement)) up.value = false
}
function focusOut(e) {
  if (hoverCapable && !el.value?.contains(e.relatedTarget)) up.value = false
}
</script>

<template>
  <div
    ref="el"
    class="dock absolute inset-x-0 bottom-0 z-20 flex h-[88px] items-end justify-center"
    :data-up="up"
    @mouseenter="enter"
    @mouseleave="leave"
    @focusin="enter"
    @focusout="focusOut"
    @click="emit('close')"
  >
    <div class="dock-inner obs-ghost flex items-center gap-1 whitespace-nowrap border border-hairline px-2 py-1.5 font-mono text-[12px] text-foreground" @click.stop>
      <button
        type="button"
        :title="t('viewer.prevTitle')"
        :aria-label="t('viewer.prev')"
        class="obs-tr flex h-8 w-8 items-center justify-center text-muted-foreground hover:text-amber-bright"
        @click="emit('go', -1)"
      ><PhCaretLeft class="h-4 w-4" aria-hidden="true" /></button>
      <span class="px-1.5">
        <i18n-t scope="global" keypath="viewer.counter">
          <template #n><span class="text-amber-bright tabular-nums">{{ index + 1 }}</span></template>
          <template #total><span class="tabular-nums">{{ total }}</span></template>
        </i18n-t><span class="text-muted-foreground" translate="no"> ・ {{ time }}</span>
      </span>
      <button
        type="button"
        :title="t('viewer.nextTitle')"
        :aria-label="t('viewer.next')"
        class="obs-tr flex h-8 w-8 items-center justify-center text-muted-foreground hover:text-amber-bright"
        @click="emit('go', 1)"
      ><PhCaretRight class="h-4 w-4" aria-hidden="true" /></button>
    </div>
  </div>
</template>

<style scoped>
/* Only devices that can hover get the retracting dock: 100% pushes it just off the bottom edge, and the hot zone or focus lifts it to 16px above the bottom.
   On touch (hover: none) it stays out permanently. */
.dock-inner {
  transform: translateY(-16px);
  transition: transform 180ms var(--ease-fluid);
}
@media (hover: hover) {
  .dock-inner { transform: translateY(100%); }
  .dock[data-up="true"] .dock-inner { transform: translateY(-16px); }
}
</style>
