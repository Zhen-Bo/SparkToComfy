<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PhCaretLeft, PhCaretRight } from '@phosphor-icons/vue'
import { hoverCapable } from '@/lib/pointer'

const { t } = useI18n()

defineProps({
  index: { type: Number, required: true },
  total: { type: Number, required: true },
  time: { type: String, required: true },
})
const emit = defineEmits(['go', 'close'])

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
    class="dock absolute inset-x-0 bottom-0 z-20 flex h-[88px] items-end justify-center max-[959px]:hidden"
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
        class="dock-btn obs-tr flex h-8 w-8 items-center justify-center text-muted-foreground hover:text-amber-bright"
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
        class="dock-btn obs-tr flex h-8 w-8 items-center justify-center text-muted-foreground hover:text-amber-bright"
        @click="emit('go', 1)"
      ><PhCaretRight class="h-4 w-4" aria-hidden="true" /></button>
    </div>
  </div>
</template>

<style scoped>
/* The coarse-pointer rule must override hover on hybrids, matching hoverCapable above. */
.dock-inner {
  transform: translateY(-16px);
  transition: transform 180ms var(--ease-fluid);
}
@media (hover: hover) {
  .dock-inner { transform: translateY(100%); }
  .dock[data-up="true"] .dock-inner { transform: translateY(-16px); }
}
@media (any-pointer: coarse) {
  .dock-inner,
  .dock[data-up="true"] .dock-inner { transform: translateY(-16px); }
  /* The swipe replaces the carets on touch, so only the counter stays */
  .dock-btn { display: none; }
}
</style>
