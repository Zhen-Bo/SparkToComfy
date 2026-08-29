/** The lifecycle of one generation: submit, stage phase, progress, preview, outcome. */

import { computed, reactive, watch } from 'vue'
import { cancelJob, fetchJob, preloadImage, submitGeneration } from '@/api/comfy'
import { JOB_STATUS, JOB_STATUSES } from '@/api/ws-contract.generated'
import { i18n } from '@/i18n'
import { catalog, currentDims } from '@/stores/catalog'
import { history, refreshHistory } from '@/stores/history'
import { errorText, notifyError } from '@/stores/notify'

const { t } = i18n.global

/** Phases where cancel means something.
 * Pressing it in any other phase does nothing. */
const CANCELLABLE = ['preparing', 'queued', 'generating', 'upscaling']

export const run = reactive({
  /* Outcome of the last run: null, { kind: 'error', reason } or { kind: 'cancelled' }.
     Failure and cancellation are the only two phases in this product that leave no evidence on screen.
     A toast is gone in 2.2 seconds, and someone who stepped away cannot tell "it failed" from "I never pressed it".
     This survives until the next run starts or the user dismisses it. */
  lastOutcome: null,
  /* Snapshot of {workflowId, params} at submit time, so retry resends exactly that.
     Resending the current panel values would make the word retry a lie once the user has edited a parameter after the failure. */
  lastRun: null,

  promptId: null,
  currentImage: null, // output image URL, or null
  previewFrame: null, // data URL of the newest preview, or null; only the newest is kept

  // Five stage phases: idle, queued/preparing, generating, upscaling, transfer, idle
  busy: false,
  phase: 'idle',
  queueAhead: null,
  queueEtaSeconds: null,
  progress: null, // { step, total }
})

/* When the output dimensions change the viewfinder changes shape, the old image is at the wrong ratio, and the stage clears back to the crosshair.
   The test is the dimensions themselves, not which control was touched.
   It never clears while generating, so preview frames in flight survive. */
watch(
  () => `${currentDims.value.width}×${currentDims.value.height}`,
  () => {
    if (run.busy) return
    run.currentImage = null
    run.previewFrame = null
  },
)

/* The single source of truth for "locked while generating".
   Every entry that can change currentDims reads this one: the size buttons, the workflow picker and a history restore.
   A second parallel busy flag would be a second truth that can drift. */
export const locked = computed(() => run.busy)

export const queueEta = computed(() => {
  const s = run.queueEtaSeconds
  if (s == null) return '--:--'
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.round(s % 60)).padStart(2, '0')}`
})

function resetRun() {
  run.phase = 'idle'
  run.busy = false
  run.progress = null
  run.previewFrame = null
  run.queueAhead = null
  run.queueEtaSeconds = null
}

export async function generate() {
  if (run.busy) return
  run.busy = true
  run.phase = 'preparing'
  run.promptId = null // the POST response supplies the identity; the receipt only repeats it
  run.progress = null
  run.previewFrame = null
  run.currentImage = null
  run.queueAhead = null
  run.queueEtaSeconds = null
  run.lastOutcome = null // a new run replaces the previous outcome
  run.lastRun = { workflowId: catalog.workflowId, params: JSON.parse(JSON.stringify(catalog.params)) }
  try {
    const { promptId } = await submitGeneration({ workflowId: catalog.workflowId, params: catalog.params })
    // The receipt may already have arrived over the socket; either source is fine, as long as this is still the same run.
    if (run.busy && run.promptId === null) run.promptId = promptId
  } catch (err) {
    console.error('[generate] submit failed', err)
    run.lastOutcome = { kind: 'error', reason: errorText(err.code) }
    resetRun()
  }
}

export function dismissOutcome() {
  run.lastOutcome = null
}

/** Resend with the original parameters of the failed run.
 * If the workflow no longer exists it says so and stops, the same all-or-nothing rule as a history restore. */
export function retryLastRun() {
  const last = run.lastRun
  if (!last || run.busy) return
  if (!catalog.workflows.some((w) => w.id === last.workflowId)) {
    return notifyError(t('notify.retryWorkflowGone'))
  }
  catalog.workflowId = last.workflowId
  catalog.params = JSON.parse(JSON.stringify(last.params))
  catalog.restoredBaseline = null
  generate()
}

/* A 204 only means the abort was sent, not that it stopped.
   Stay locked until the terminal WebSocket event unlocks it. */
export async function cancelRun() {
  if (run.promptId === null) return
  if (!CANCELLABLE.includes(run.phase)) return
  run.phase = 'cancelling'
  run.progress = null
  run.previewFrame = null
  run.queueAhead = null
  run.queueEtaSeconds = null
  try {
    await cancelJob(run.promptId)
  } catch (err) {
    console.error('[cancel] submit failed', err)
    notifyError(t('notify.cancelFailed', { reason: errorText(err.code) }))
  }
}

/* A seed locked at -1 gets the resolved value written back into the field after a successful run, the NovelAI convention.
   Only while locked: an unlocked -1 means "random again next time", and writing it back would change what the user asked for.
   Only the backend knows the resolved value, so it comes from params.seed, a string, on the matching history entry. */
function writeBackSeed(entries) {
  if (!catalog.seedLocked || Number(catalog.params.seed) !== -1) return
  const realized = Number(entries.find((h) => h.promptId === run.promptId)?.params?.seed)
  if (Number.isInteger(realized) && realized >= 0) catalog.params.seed = realized
}

/* The transfer phase: the scan line keeps running until the output image has really loaded.
   History and the image are written in the same update, so both reach the screen at the same moment rather than one after the other.
   The backend writes history before it broadcasts done (succeed in app/jobs/events.py), so the entry is always there by now. allSettled keeps one failure from taking the other down, and means this never rejects, which matters because onJob does not await it. */
async function finish(images) {
  run.phase = 'transfer'
  const url = images[0]
  const [img] = await Promise.allSettled([preloadImage(url), refreshHistory()])
  if (img.status === 'fulfilled') run.currentImage = url
  else {
    console.error('[image] output image failed to load', img.reason)
    // The stage falls back to an empty canvas, so this is another outcome with no visual evidence: it goes to the bottom bar rather than a toast.
    run.lastOutcome = { kind: 'error', reason: errorText(img.reason?.code) }
  }
  writeBackSeed(history.entries)
  resetRun()
}

/**
 * A job whose outcome may have passed while the socket was dead.
 * The backend does not replay terminal messages, so its job record is the only way to tell.
 * Still in flight: the replay that follows system re-attaches it, nothing to do here.
 * Done or failed: finish it here exactly as the socket message would have.
 * No record: a cancelled job leaves none.
 */
export async function settleFromServer() {
  const promptId = run.promptId
  if (promptId === null) return // the POST has not answered yet; it brings the id
  let job
  try {
    job = await fetchJob(promptId)
  } catch (err) {
    if (err.status !== 404) return console.error('[run] job lookup failed', err)
    job = { status: JOB_STATUS.CANCELLED }
  }
  // A socket message may have settled this run while the lookup was in flight.
  if (!run.busy || run.promptId !== promptId) return
  if (job.status === JOB_STATUS.QUEUED || job.status === JOB_STATUS.RUNNING) return
  onJob(job.status === JOB_STATUS.ERROR ? { status: job.status, code: job.error } : job)
}

export function onReceipt({ promptId }) {
  run.promptId = promptId
}

/* One handler per terminal state.
   The status strings come from the generated contract file, and app/ws/schemas.py is the only place they are declared.
   To add a state: change the schema, run the codegen, add a row here.
   A test fails for every step that is missed. */
const JOB_HANDLERS = {
  [JOB_STATUS.QUEUED]: (job) => {
    if (run.phase === 'cancelling') return
    run.busy = true
    run.phase = 'queued'
    run.queueAhead = job.position
    run.queueEtaSeconds = job.etaSeconds
  },
  [JOB_STATUS.RUNNING]: () => {
    if (run.phase === 'cancelling') return
    run.busy = true
    if (run.phase === 'idle' || run.phase === 'queued') run.phase = 'preparing'
    run.queueAhead = null
    run.queueEtaSeconds = null
  },
  [JOB_STATUS.DONE]: (job) => finish(job.images),
  [JOB_STATUS.ERROR]: (job) => {
    run.lastOutcome = { kind: 'error', reason: errorText(job.code) }
    resetRun()
  },
  [JOB_STATUS.CANCELLED]: () => {
    run.lastOutcome = { kind: 'cancelled' }
    resetRun()
  },
}

const missing = JOB_STATUSES.filter((s) => !(s in JOB_HANDLERS))
if (missing.length) throw new Error(`job statuses with no handler: ${missing.join(', ')}`)

export function onJob(job) {
  return JOB_HANDLERS[job.status]?.(job)
}

export function onProgress({ step, total }) {
  if (run.phase === 'cancelling') return
  run.progress = { step, total }
  if (step >= total) run.phase = 'upscaling'
}

export function onPreview({ url }) {
  if (run.phase === 'cancelling') return
  run.previewFrame = url
  if (run.phase === 'preparing' || run.phase === 'queued') run.phase = 'generating'
}
