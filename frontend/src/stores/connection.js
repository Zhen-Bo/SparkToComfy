/** Connection state and startup: is the WebSocket up, is the engine up, how long has it been offline, when is the next retry. */

import { reactive } from 'vue'
import { connectEvents, fetchHistory, fetchWorkflows } from '@/api/comfy'
import { i18n } from '@/i18n'
import { catalog, selectWorkflow } from '@/stores/catalog'
import { history } from '@/stores/history'
import { errorText, notify } from '@/stores/notify'
import { onJob, onPreview, onProgress, onReceipt, run, settleFromHistory } from '@/stores/run'

const { t } = i18n.global

export const connection = reactive({
  comfyOnline: false,
  // Connected means the WebSocket is up: onClose clears it, onSystem sets it, and system always arrives first on every connect.
  wsOnline: false,
  // Offline measurement starts when comfyOnline turns false; it feeds the readout on the overlay card.
  offlineSince: null, // epoch ms, null while online
  // Every dropped WebSocket counts as one retry; api/comfy.js owns the backoff.
  reconnectAttempts: 0,
  // epoch ms of the next WebSocket retry while the backend is down, used by the countdown on the overlay
  nextRetryAt: null,
})

/* system always arrives first on a connect, so it is the signal that we are connected.
   If a run is still busy, history is checked once: found means it finished while we were disconnected, so the image completes; not found means it is still running and we wait for the receipt. */
function onSystem({ comfyOnline }) {
  connection.comfyOnline = comfyOnline
  connection.wsOnline = true
  connection.nextRetryAt = null // system arrived, so the socket is up and nothing is pending
  if (comfyOnline) {
    connection.offlineSince = null
    connection.reconnectAttempts = 0
    // Catch up after the backend returns: if the HTTP bootstrap failed at startup the workflow list is still empty, so fetch the catalog and history once connected.
    if (!catalog.workflows.length) void bootstrap()
  } else if (connection.offlineSince === null) {
    // The socket is up but the engine went down: offline starts counting here.
    connection.offlineSince = Date.now()
  }
  if (run.busy) settleFromHistory()
}

function onWSClose({ nextRetryMs } = {}) {
  const wasOnline = connection.wsOnline
  connection.wsOnline = false
  connection.comfyOnline = false // With the socket gone, whether ComfyUI is up is unknown; do not keep a stale value.
  if (connection.offlineSince === null) connection.offlineSince = Date.now()
  // The first drop counts as 1; every failed reconnect after that adds one.
  // api/comfy.js decides the backoff interval.
  connection.reconnectAttempts = wasOnline ? 1 : connection.reconnectAttempts + 1
  connection.nextRetryAt = nextRetryMs ? Date.now() + nextRetryMs : null
}

/** HTTP bootstrap: catalog plus history.
 * It runs at startup, and onSystem runs it again when the backend returns, so the first workflow is selected only when none was chosen yet. */
async function bootstrap() {
  try {
    catalog.workflows = await fetchWorkflows()
    if (catalog.workflows.length && catalog.workflowId == null) selectWorkflow(catalog.workflows[0].id)
    const { items, limit } = await fetchHistory()
    history.entries = items
    if (limit !== null) history.limit = limit
  } catch (err) {
    console.error('[init] failed to load', err)
    notify(t('notify.loadFailed', { reason: errorText(err.code) }))
  }
}

export async function initStudio() {
  // The event line opens unconditionally: a failed HTTP bootstrap, with the backend down, must not take the socket with it.
  // The reconnect loop and the offline overlay readouts exist only through it, and onSystem reruns the bootstrap once the backend is back.
  connectEvents({ onReceipt, onJob, onProgress, onPreview, onSystem, onClose: onWSClose })
  await bootstrap()
}
