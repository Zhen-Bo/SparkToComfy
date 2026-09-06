import { reactive } from 'vue'
import { connectEvents, fetchHistory, fetchWorkflows } from '@/api/comfy'
import { i18n } from '@/i18n'
import { catalog, selectWorkflow } from '@/stores/catalog'
import { history } from '@/stores/history'
import { errorText, notifyError } from '@/stores/notify'
import { onJob, onPreview, onProgress, onReceipt, run, settleFromServer } from '@/stores/run'

const { t } = i18n.global

export const connection = reactive({
  comfyOnline: false,
  wsOnline: false,
  offlineSince: null, // epoch ms, null while online
  // Every dropped WebSocket counts as one retry; api/comfy.js owns the backoff.
  reconnectAttempts: 0,
  // epoch ms of the next WebSocket retry while the backend is down, used by the countdown on the overlay
  nextRetryAt: null,
})

/* The first system message confirms connectivity. Query busy jobs to recover outcomes missed offline. */
function onSystem({ comfyOnline }) {
  connection.comfyOnline = comfyOnline
  connection.wsOnline = true
  connection.nextRetryAt = null
  if (comfyOnline) {
    connection.offlineSince = null
    connection.reconnectAttempts = 0
    // Retry an initial HTTP bootstrap that failed while the backend was unavailable.
    if (!catalog.workflows.length) void bootstrap()
  } else if (connection.offlineSince === null) {
    connection.offlineSince = Date.now()
  }
  if (run.busy) settleFromServer()
}

function onWSClose({ nextRetryMs } = {}) {
  const wasOnline = connection.wsOnline
  connection.wsOnline = false
  connection.comfyOnline = false // With the socket gone, whether ComfyUI is up is unknown; do not keep a stale value.
  if (connection.offlineSince === null) connection.offlineSince = Date.now()
  connection.reconnectAttempts = wasOnline ? 1 : connection.reconnectAttempts + 1
  connection.nextRetryAt = nextRetryMs ? Date.now() + nextRetryMs : null
}

// Reconnect may rerun bootstrap; preserve an existing workflow selection.
async function bootstrap() {
  try {
    catalog.workflows = await fetchWorkflows()
    if (catalog.workflows.length && catalog.workflowId == null) selectWorkflow(catalog.workflows[0].id)
    const { items, limit } = await fetchHistory()
    history.entries = items
    if (limit !== null) history.limit = limit
  } catch (err) {
    console.error('[init] failed to load', err)
    notifyError(t('notify.loadFailed', { reason: errorText(err.code) }))
  }
}

export async function initStudio() {
  // Start reconnect handling even if the HTTP bootstrap fails.
  connectEvents({ onReceipt, onJob, onProgress, onPreview, onSystem, onClose: onWSClose })
  await bootstrap()
}
