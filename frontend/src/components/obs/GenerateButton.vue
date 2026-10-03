<script setup>
/* Use aria-disabled to preserve focus across job-state changes; onClick enforces it.
   Demo mode simulates activity locally without submitting a job. */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { connection } from '@/stores/connection'
import { cancelRun, generate, run } from '@/stores/run'
import { cn } from '@/lib/utils'
import { MOD_KEY, isGenerateShortcut } from '@/lib/shortcut'
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
// Only the state that starts a job is tinted; locked and cancel states stay plain outlines
const ready = computed(() => !locked.value && !destructive.value)

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

/* The shortcut only ever starts a job: while one runs it does nothing, so a repeated press can never cancel.
   An open dialog owns the keyboard, and an offline Comfy is the same gate the button's inert wrapper applies. */
const pressed = ref(false)
let pressTimer = 0
function onShortcut(e) {
  if (!isGenerateShortcut(e)) return
  if (document.querySelector('[aria-modal="true"]')) return
  e.preventDefault()
  if (!ready.value || run.busy || !connection.comfyOnline) return
  pressed.value = true
  clearTimeout(pressTimer)
  pressTimer = setTimeout(() => { pressed.value = false }, 140)
  generate()
}
onMounted(() => { if (!props.demo) document.addEventListener('keydown', onShortcut) })
onUnmounted(() => {
  document.removeEventListener('keydown', onShortcut)
  clearTimeout(pressTimer)
})
</script>

<template>
  <button
    type="button"
    :aria-disabled="locked"
    :aria-haspopup="destructive ? 'dialog' : undefined"
    :aria-keyshortcuts="demo ? undefined : MOD_KEY.aria"
    :title="ready && !demo ? `${label} (${MOD_KEY.label}+Enter)` : undefined"
    :class="cn(
      'obs-tr relative w-full rounded-sm border py-3 font-disp text-[13px] font-semibold tracking-[.2em]',
      locked && 'cursor-not-allowed border-amber-dim bg-transparent text-amber',
      destructive && 'border-destructive bg-transparent text-destructive hover:bg-destructive/10 active:scale-[.98]',
      // A tinted outline, not a fill: the panel's primary action without becoming the brightest thing on screen
      ready && 'border-amber bg-amber/10 text-amber-bright hover:bg-amber/20 active:scale-[.98]',
      pressed && 'scale-[.98]',
      $attrs.class,
    )"
    @click="onClick"
  >
    {{ label }}
    <!-- Shown only where a keyboard is likely; the touch layout has no use for it -->
    <span
      v-if="ready && !demo"
      class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[11px] font-normal tracking-normal opacity-60 max-[959px]:hidden"
      aria-hidden="true"
      translate="no"
    >{{ MOD_KEY.label }} ↵</span>
  </button>

  <CancelRunDialog
    v-if="confirming"
    :phase="run.phase"
    :progress="run.progress"
    @confirm="onConfirmCancel"
    @cancel="confirming = false"
  />
</template>
