import { reactive } from 'vue'
import { i18n } from '@/i18n'

const { t, te } = i18n.global

const NOTICE_MS = 2200
const ACTION_MS = 6000 // long enough to reach an action button such as Undo

export const toast = reactive({
  notice: null,
  // Errors persist so users can read them after returning to the page.
  sticky: false,
  action: null, // { label, run } renders a button inside the notice
})

// Preserve unknown codes for diagnosis; errors without a code use the generic message.
export const errorText = (code) => (code && te(`errors.${code}`) ? t(`errors.${code}`) : (code ?? t('errors.unexpected')))

let noticeTimer = null

/** Show a transient notice, optionally with one action such as Undo. */
export function notify(msg, action = null) {
  show(msg, false, action)
}

/** Show an error until dismissed or replaced by another notice. */
export function notifyError(msg) {
  show(msg, true)
}

export function dismissNotice() {
  clearTimeout(noticeTimer)
  toast.notice = null
  toast.sticky = false
  toast.action = null
}

/** Dismiss first, so the action may show its own notice. */
export function runNoticeAction() {
  const action = toast.action
  dismissNotice()
  action?.run()
}

function show(msg, sticky, action = null) {
  clearTimeout(noticeTimer)
  toast.notice = msg
  toast.sticky = sticky
  toast.action = action
  if (sticky) return
  noticeTimer = setTimeout(dismissNotice, action ? ACTION_MS : NOTICE_MS)
}
