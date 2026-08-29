/** Global toasts and the text for each error code.
 * Anyone may call it; it depends on no other store. */

import { reactive } from 'vue'
import { i18n } from '@/i18n'

// Translation entry for non-component modules.
// The locale follows the browser and never changes at runtime, so the global composer is enough.
const { t, te } = i18n.global

const NOTICE_MS = 2200

export const toast = reactive({
  notice: null,
  // A failure holds until the user closes it. 2.2 seconds is not evidence: look away once and the only account of what went wrong is gone,
  // and nothing can bring it back. This is the same reason the stage keeps a standing outcome bar instead of a toast.
  sticky: false,
})

// Error text lives in i18n under `errors.*`.
// An undefined code means what was thrown is not an ApiError, so it is a bug of our own; the API layer already turns an unreachable backend into network_error.
// An unknown code is shown as-is rather than swallowed.
export const errorText = (code) => (code && te(`errors.${code}`) ? t(`errors.${code}`) : (code ?? t('errors.unexpected')))

let noticeTimer = null

/** Something went right, or something the user just did. It leaves on its own. */
export function notify(msg) {
  show(msg, false)
}

/** Something went wrong. It stays on screen with a close control until the user dismisses it or a newer notice replaces it. */
export function notifyError(msg) {
  show(msg, true)
}

export function dismissNotice() {
  clearTimeout(noticeTimer)
  toast.notice = null
  toast.sticky = false
}

function show(msg, sticky) {
  clearTimeout(noticeTimer)
  toast.notice = msg
  toast.sticky = sticky
  if (sticky) return
  noticeTimer = setTimeout(() => {
    toast.notice = null
  }, NOTICE_MS)
}
