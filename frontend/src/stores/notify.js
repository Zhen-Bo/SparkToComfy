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
})

// Error text lives in i18n under `errors.*`.
// An undefined code means what was thrown is not an ApiError, so it is a bug of our own; the API layer already turns an unreachable backend into network_error.
// An unknown code is shown as-is rather than swallowed.
export const errorText = (code) => (code && te(`errors.${code}`) ? t(`errors.${code}`) : (code ?? t('errors.unexpected')))

let noticeTimer = null
export function notify(msg) {
  toast.notice = msg
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => {
    toast.notice = null
  }, NOTICE_MS)
}
