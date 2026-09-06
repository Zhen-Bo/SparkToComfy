import { reactive } from 'vue'
import { i18n } from '@/i18n'

const { t, te } = i18n.global

const NOTICE_MS = 2200

export const toast = reactive({
  notice: null,
  // Errors persist so users can read them after returning to the page.
  sticky: false,
})

// Preserve unknown codes for diagnosis; errors without a code use the generic message.
export const errorText = (code) => (code && te(`errors.${code}`) ? t(`errors.${code}`) : (code ?? t('errors.unexpected')))

let noticeTimer = null

/** Show a transient notice. */
export function notify(msg) {
  show(msg, false)
}

/** Show an error until dismissed or replaced by another notice. */
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
