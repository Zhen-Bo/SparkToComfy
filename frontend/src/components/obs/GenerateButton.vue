<script setup>
/* Use aria-disabled to preserve focus across job-state changes; onClick enforces it.
   Demo mode simulates activity locally without submitting a job. */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { connection } from '@/stores/connection'
import { cancelRun, generate, run } from '@/stores/run'
import { cn } from '@/lib/utils'
import CancelRunDialog from '@/components/obs/CancelRunDialog.vue'

// Two root nodes (button + dialog), so attrs cannot auto-inherit: the host's class goes on the button explicitly.
defineOptions({ inheritAttrs: false })

const { t } = useI18n()

const props = defineProps({
  demo: { type: Boolean, default: false },
})

const demoBusy = ref(false)
function runDemo() {
  if (demoBusy.value) return
  demoBusy.value = true
  setTimeout(() => { demoBusy.value = false }, 2200)
}

const LOCKED_PHASES = new Set(['cancelling', 'transfer'])
const locked = computed(() =>
  props.demo
    ? demoBusy.value
    : !connection.wsOnline ||
      (run.busy && (run.promptId === null || LOCKED_PHASES.has(run.phase))),
)

const CANCELLABLE = new Set(['queued', 'preparing', 'generating', 'upscaling'])
const destructive = computed(() => !props.demo && run.busy && CANCELLABLE.has(run.phase) && !locked.value)

const confirming = ref(false)
// Dismiss the confirmation if the job stops being cancellable while the dialog is open.
watch(() => [run.busy, run.phase], () => {
  if (!run.busy || !CANCELLABLE.has(run.phase)) confirming.value = false
})

const BUSY_LABEL = { cancelling: 'generate.cancelling', transfer: 'generate.transfer', queued: 'generate.cancelQueue' }
const demoLabel = () => t(demoBusy.value ? 'generate.busy' : 'generate.start')

const label = computed(() => {
  if (props.demo) return demoLabel()
  if (!connection.wsOnline) return t('generate.connecting')
  if (!run.busy) return t('generate.start')
  if (run.promptId === null) return t('generate.preparing')
  return t(BUSY_LABEL[run.phase] ?? 'generate.cancelGeneration')
})

function onClick() {
  if (props.demo) return runDemo()
  if (locked.value) return
  if (!run.busy) return generate()
  confirming.value = true
}

function onConfirmCancel() {
  confirming.value = false
  cancelRun()
}
</script>

<template>
  <button
    type="button"
    :aria-disabled="locked"
    :aria-haspopup="destructive ? 'dialog' : undefined"
    :class="cn(
      'obs-tr w-full rounded-sm border bg-transparent py-3 font-disp text-[11px] tracking-[.34em]',
      locked && 'cursor-not-allowed border-amber-dim text-amber',
      destructive && 'border-destructive text-destructive hover:bg-destructive/10 active:scale-[.98]',
      !locked && !destructive && 'border-amber text-amber hover:bg-amber/10 hover:text-amber-bright active:scale-[.98]',
      $attrs.class,
    )"
    @click="onClick"
  >{{ label }}</button>

  <CancelRunDialog
    v-if="confirming"
    :phase="run.phase"
    :progress="run.progress"
    @confirm="onConfirmCancel"
    @cancel="confirming = false"
  />
</template>
