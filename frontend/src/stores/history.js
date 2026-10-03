import { reactive } from 'vue'
import { clearHistory as clearHistoryApi, deleteHistoryEntry as deleteEntryApi, fetchHistory } from '@/api/comfy'
import { INTL_LOCALE, i18n } from '@/i18n'
import { catalog, sizeOf } from '@/stores/catalog'
import { errorText, notify, notifyError } from '@/stores/notify'
import { run } from '@/stores/run'

const { t } = i18n.global

export const history = reactive({
  entries: [],
  // Backend history cap; null until known so the readout can show a dash.
  limit: null,
})

const TIME_FMT = new Intl.DateTimeFormat(INTL_LOCALE, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
export const timeOf = (iso) => TIME_FMT.format(new Date(iso))

/* Some callers do not await this refresh; handle failures here so they are reported to the user. */
export async function refreshHistory() {
  try {
    const { items, limit } = await fetchHistory()
    history.entries = items
    if (limit !== null) history.limit = limit
  } catch (err) {
    console.error('[history] failed to load', err)
    notifyError(t('notify.historyLoadFailed', { reason: errorText(err.code) }))
  }
}

// Deep copy through JSON: reactive proxies make structuredClone throw, and parameters are JSON data to begin with.
const clone = (value) => JSON.parse(JSON.stringify(value))

// Guard every caller against changing the workflow and frame dimensions during a run.
export function restoreFromHistory(entry) {
  if (run.busy) return notifyError(t('notify.restoreBusy'))
  if (!catalog.workflows.some((w) => w.id === entry.workflowId)) {
    return notifyError(t('notify.workflowGone'))
  }
  const before = clone({ workflowId: catalog.workflowId, params: catalog.params, restoredBaseline: catalog.restoredBaseline })
  catalog.workflowId = entry.workflowId
  catalog.params = { ...clone(entry.params), seed: Number(entry.params.seed) }
  catalog.restoredBaseline = clone(catalog.params)
  const d = sizeOf(entry.workflowId, entry.params.size)
  notify(
    t('notify.restored', {
      seed: catalog.params.seed,
      width: d?.width ?? '—',
      height: d?.height ?? '—',
      steps: catalog.params.steps,
      cfg: catalog.params.cfg,
    }),
    { label: t('notify.undo'), run: () => undoRestore(before) },
  )
}

function undoRestore(before) {
  if (run.busy) return notifyError(t('notify.undoBusy'))
  Object.assign(catalog, before)
  notify(t('notify.restoreUndone'))
}

export async function clearHistory() {
  try {
    await clearHistoryApi()
    history.entries = []
    notify(t('notify.cleared'))
  } catch (err) {
    console.error('[history] failed to clear', err)
    notifyError(t('notify.historyClearFailed', { reason: errorText(err.code) }))
  }
}

export async function deleteHistoryEntry(promptId) {
  try {
    await deleteEntryApi(promptId)
    history.entries = history.entries.filter((e) => e.promptId !== promptId)
    notify(t('notify.entryDeleted'))
    return true
  } catch (err) {
    console.error('[history] failed to delete entry', err)
    notifyError(t('notify.entryDeleteFailed', { reason: errorText(err.code) }))
    return false
  }
}
