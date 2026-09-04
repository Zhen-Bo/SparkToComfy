<script setup>
/**
 * The one main action button: start generating while idle, cancel while busy.
 * Four cases make it unavailable: the socket is down (HTTP would still send but no progress could come back), promptId is not known yet (the cancel API cannot be called), a cancel was already sent, and the transfer phase (cancelling means nothing there).
 * Unavailable always means aria-disabled, never the native disabled attribute, because native disabled evaporates the keyboard focus that just pressed it onto body.
 * The aria-disabled contract must then hold: onClick returns early while locked, so the action really is a no-op.
 * Otherwise a button that says it cannot be pressed would submit a generation and follow it with a failure toast.
 *
 * Cancelling asks first.
 * While busy this button is destructive, so it turns the destructive colour and a press only opens CancelRunDialog; confirm cancels.
 * The confirmation vocabulary is the one used for clearing all history, because both are irreversible and both throw work away.
 * Position, width and count never change.
 *
 * Demo mode, used by the /playground overview, only plays its own busy and recovery.
 * It starts no generation, writes no store and touches no other row, matching the pg-matrix rule that rows never drive each other.
*/
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

/** Phases where a press destroys something: the button is red and asks first. */
const CANCELLABLE = new Set(['queued', 'preparing', 'generating', 'upscaling'])
const destructive = computed(() => !props.demo && run.busy && CANCELLABLE.has(run.phase) && !locked.value)

const confirming = ref(false)
// Close the confirmation once the job ends on its own, or is already cancelling: never leave an overlay asking to cancel something that no longer exists.
watch(() => [run.busy, run.phase], () => {
  if (!run.busy || !CANCELLABLE.has(run.phase)) confirming.value = false
})

/** Busy labels by phase. Any phase not listed is a running generation, which the press cancels. */
const BUSY_LABEL = { cancelling: 'generate.cancelling', transfer: 'generate.transfer', queued: 'generate.cancelQueue' }
const demoLabel = () => t(demoBusy.value ? 'generate.busy' : 'generate.start')

const label = computed(() => {
  if (props.demo) return demoLabel()
  if (!connection.wsOnline) return t('generate.connecting') // includes the first load: not connected until the first system arrives
  if (!run.busy) return t('generate.start')
  if (run.promptId === null) return t('generate.preparing')
  return t(BUSY_LABEL[run.phase] ?? 'generate.cancelGeneration')
})

function onClick() {
  if (props.demo) return runDemo()
  if (locked.value) return // aria-disabled means the action must be a no-op; the inner guard only blocks repeat submits
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
