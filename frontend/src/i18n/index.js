/**
 * The vue-i18n instance.
 * The language follows navigator.language only: there is no switcher UI and nothing is written to localStorage.
 * English is the fixed fallback for any key a locale file is missing.
 * Components use t from useI18n(); stores, the router and lib modules use i18n.global.t.
 * Parameter control names live under params.*, because the backend sends no label and the control key it returns is the i18n key.
 * Only data still comes through from the backend verbatim: workflow names, dropdown and LoRA option labels, and size presets such as 1:1.
 * Those read the same in every language and stay out of the locale files.
*/
import { createI18n } from 'vue-i18n'
import zhTW from './locales/zh-TW'
import zhCN from './locales/zh-CN'
import en from './locales/en'

/** Browser language to supported locale: zh by region or script (TW/HK/MO/Hant to Traditional, everything else to Simplified); anything not zh becomes en. */
export function detectLocale() {
  const tag = (navigator.language || 'en').toLowerCase()
  if (!tag.startsWith('zh')) return 'en'
  if (tag.includes('hant')) return 'zh-TW'
  return ['zh-tw', 'zh-hk', 'zh-mo'].some((r) => tag.startsWith(r)) ? 'zh-TW' : 'zh-CN'
}

/** The detected tag is usable directly with the Intl API, DateTimeFormat and friends. */
export const INTL_LOCALE = detectLocale()

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: INTL_LOCALE,
  fallbackLocale: 'en',
  messages: { 'zh-TW': zhTW, 'zh-CN': zhCN, en },
})

document.documentElement.lang = { 'zh-TW': 'zh-Hant', 'zh-CN': 'zh-Hans', en: 'en' }[INTL_LOCALE]
