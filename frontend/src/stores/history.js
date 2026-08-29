/** The history list: load, restore, clear.
 * The cap comes from a backend response header, never hardcoded here. */

import { reactive } from 'vue'
import { clearHistory as clearHistoryApi, fetchHistory } from '@/api/comfy'
import { INTL_LOCALE, i18n } from '@/i18n'
import { catalog, sizeOf } from '@/stores/catalog'
import { errorText, notify, notifyError } from '@/stores/notify'
import { run } from '@/stores/run'

const { t } = i18n.global

export const history = reactive({
  entries: [],
  /* How many rows the backend returns at most (HISTORY_LIMIT in app/database.py, sent down as X-History-Limit).
     It stays null until asked: the readout shows a dash rather than a guessed number, the same rule as sizeOf returning null. */
  limit: null,
})

const TIME_FMT = new Intl.DateTimeFormat(INTL_LOCALE, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
export const timeOf = (iso) => TIME_FMT.format(new Date(iso))

/* onJob is a synchronous switch and nobody awaits the promises returned by finish and resumeFromHistory, so nothing inside them may reject: it would become an unhandled rejection that the screen never shows. */
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

/** Restore every parameter from a history entry so the image can be reproduced.
    Not while generating: restoring swaps the workflow and the size, the viewfinder aspect ratio follows, and preview frames still arriving at the old ratio would be forced into the new frame.
    This is the reason RatioSelector locks too, and guarding at the write point is what covers every entry into it. */
export function restoreFromHistory(entry) {
  if (run.busy) return notifyError(t('notify.restoreBusy'))
  if (!catalog.workflows.some((w) => w.id === entry.workflowId)) {
    return notifyError(t('notify.workflowGone'))
  }
  catalog.workflowId = entry.workflowId
  // Deep copy through JSON: entry is a reactive proxy and structuredClone rejects proxies, while params is JSON data to begin with.
  catalog.params = { ...JSON.parse(JSON.stringify(entry.params)), seed: Number(entry.params.seed) }
  catalog.restoredBaseline = JSON.parse(JSON.stringify(catalog.params))
  const d = sizeOf(entry.workflowId, entry.params.size)
  notify(
    t('notify.restored', {
      seed: catalog.params.seed,
      width: d?.width ?? '—',
      height: d?.height ?? '—',
      steps: catalog.params.steps,
      cfg: catalog.params.cfg,
    }),
  )
}

/** Clear all history.
 * The screen is cleared only after the backend soft delete succeeds; on failure the entries stay and the user is told. */
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
