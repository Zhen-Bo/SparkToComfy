<script setup>
/**
 * Full-page confirmation (alertdialog) for cancelling the current job.
 * Structure and interaction copy ClearHistoryDialog exactly.
 * Both destroy something irreversibly, so there should not be a second confirmation vocabulary: a mask plus a centred panel (obs-elevated with obs-corners), focus on the safe option, keep generating; Tab cycles between the two buttons; ESC or a click on the mask keeps the job; only confirm cancels.
 * The description carries the real readout, which step it reached, for the same reason the clear dialog carries a count: a confirmation needs evidence.
*/
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useModalLayer } from '@/lib/useModalLayer'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  /** Current phase: queued, preparing, generating or upscaling. */
  phase: { type: String, required: true },
  /** Current progress as {step, total}; null in the queued and upscaling phases. */
  progress: { type: Object, default: null },
})
const emit = defineEmits(['confirm', 'cancel'])

const queued = computed(() => props.phase === 'queued' || props.phase === 'preparing')
const title = computed(() => (queued.value ? t('cancelRun.titleQueued') : t('cancelRun.titleRunning')))
const desc = computed(() => {
  if (queued.value) return t('cancelRun.descQueued')
  if (props.progress) return t('cancelRun.descProgress', { step: props.progress.step, total: props.progress.total })
  return t('cancelRun.descRunning')
})

const backBtn = ref(null)
const yesBtn = ref(null)

function onKeydown(e) {
  if (e.key === 'Escape') return emit('cancel')
  // Focus loop: two buttons cycling into each other, a second guard beside inert, the same as ClearHistoryDialog.
  if (e.key === 'Tab') {
    e.preventDefault()
    ;(document.activeElement === backBtn.value ? yesBtn : backBtn).value?.focus()
  }
}

useModalLayer(backBtn)
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[250]">
      <div class="crd-mask absolute inset-0 bg-overlay/[.82]" />
      <div class="absolute inset-0 flex items-center justify-center" @click.self="emit('cancel')">
        <div
          class="crd-panel obs-elevated obs-corners w-[340px] border border-hairline p-5 shadow-[0_12px_40px_hsl(var(--dome)/.6)]"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="crd-title"
          aria-describedby="crd-desc"
        >
          <div id="crd-title" class="font-sans text-[13.5px] font-bold tracking-[.06em] text-foreground">{{ title }}</div>
          <p id="crd-desc" class="mt-2 font-sans text-[12px] leading-[1.8] text-muted-foreground">{{ desc }}</p>
          <div class="mt-[18px] flex justify-end gap-2">
            <button
              ref="backBtn"
              type="button"
              class="obs-tr h-7 cursor-pointer rounded-sm border border-control px-3.5 font-sans text-[11.5px] font-bold tracking-[.08em] text-muted-foreground hover:border-amber hover:text-foreground active:scale-95"
              @click="emit('cancel')"
            >{{ t('cancelRun.back') }}</button>
            <button
              ref="yesBtn"
              type="button"
              class="obs-tr h-7 cursor-pointer rounded-sm border border-destructive/70 px-3.5 font-sans text-[11.5px] font-bold tracking-[.08em] text-destructive hover:border-destructive hover:bg-destructive/15 active:scale-95"
              @click="emit('confirm')"
            >{{ t('cancelRun.confirm') }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/*
  The entry animation is built in as keyframes on mount rather than left to a <Transition> around the call site.
  This component hangs under GenerateButton, GenerateButton is a multi-root fragment and this root is a Teleport, so an outer <Transition> cannot reach a root element: the enter class never comes off and the node never unmounts.
  The timing follows the dialog zoom-in in DESIGN.md: 160ms, --ease-fluid, from translateY(4px) scale(.98).
  The exit unmounts immediately.
*/
.crd-mask  { animation: crdMaskIn 160ms ease-out both; }
.crd-panel { animation: crdPanelIn 160ms var(--ease-fluid) both; }
@keyframes crdMaskIn  { from { opacity: 0; } to { opacity: 1; } }
@keyframes crdPanelIn { from { opacity: 0; transform: translateY(4px) scale(.98); } to { opacity: 1; transform: none; } }

@media (prefers-reduced-motion: reduce) {
  .crd-mask, .crd-panel { animation-duration: 1ms; }
}
</style>
