import { computed, reactive, watch } from 'vue'
import { cancelJob, fetchJob, preloadImage, submitGeneration } from '@/api/comfy'
import { JOB_STATUS, JOB_STATUSES } from '@/api/ws-contract.generated'
import { i18n } from '@/i18n'
import { catalog, currentDims } from '@/stores/catalog'
import { history, refreshHistory } from '@/stores/history'
import { errorText, notifyError } from '@/stores/notify'

const { t } = i18n.global

const CANCELLABLE = ['preparing', 'queued', 'generating', 'upscaling']

export const run = reactive({
  // Keep failures and cancellations visible until dismissed or a new run starts.
  lastOutcome: null,
  // Snapshot at submission so retry preserves the original parameters after panel edits.
  lastRun: null,

  promptId: null,
  currentImage: null, // output image URL, or null
  previewFrame: null, // data URL of the newest preview, or null; only the newest is kept

  busy: false,
  phase: 'idle',
  queueAhead: null,
  queueEtaSeconds: null,
  progress: null, // { step, total }
})

// Clear stale images when the frame dimensions change, but preserve previews during a run.
watch(
  () => `${currentDims.value.width}×${currentDims.value.height}`,
  () => {
    if (run.busy) return
    run.currentImage = null
    run.previewFrame = null
  },
)

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
  run.promptId = null
  run.progress = null
  run.previewFrame = null
  run.currentImage = null
  run.queueAhead = null
  run.queueEtaSeconds = null
  run.lastOutcome = null
  run.lastRun = { workflowId: catalog.workflowId, params: JSON.parse(JSON.stringify(catalog.params)) }
  try {
    const { promptId } = await submitGeneration({ workflowId: catalog.workflowId, params: catalog.params })
    // A socket receipt may arrive before the POST response; do not overwrite an assigned ID.
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

/* Resolve a locked random seed from backend history so it can be reused.
   Leave an unlocked -1 unchanged to request a new random seed next time. */
function writeBackSeed(entries) {
  if (!catalog.seedLocked || Number(catalog.params.seed) !== -1) return
  const realized = Number(entries.find((h) => h.promptId === run.promptId)?.params?.seed)
  if (Number.isInteger(realized) && realized >= 0) catalog.params.seed = realized
}

/* Stay in transfer until the image load and history refresh settle.
   allSettled lets either operation finish even if the other fails. */
async function finish(images) {
  run.phase = 'transfer'
  const url = images[0]
  const [img] = await Promise.allSettled([preloadImage(url), refreshHistory()])
  if (img.status === 'fulfilled') run.currentImage = url
  else {
    console.error('[image] output image failed to load', img.reason)
    run.lastOutcome = { kind: 'error', reason: errorText(img.reason?.code) }
  }
  writeBackSeed(history.entries)
  resetRun()
}

/* Recover terminal outcomes missed offline; live jobs reattach through the socket replay.
   A missing server record is treated as cancellation. */
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

/* To add a job status, update app/ws/schemas.py, regenerate the contract, and add its handler here. */
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
