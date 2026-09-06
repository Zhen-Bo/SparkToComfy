/* Detect language once at startup. Backend workflow and option labels remain verbatim. */
import { createI18n } from 'vue-i18n'
import zhTW from './locales/zh-TW'
import zhCN from './locales/zh-CN'
import en from './locales/en'

export function detectLocale() {
  const tag = (navigator.language || 'en').toLowerCase()
  if (!tag.startsWith('zh')) return 'en'
  if (tag.includes('hant')) return 'zh-TW'
  return ['zh-tw', 'zh-hk', 'zh-mo'].some((r) => tag.startsWith(r)) ? 'zh-TW' : 'zh-CN'
}

export const INTL_LOCALE = detectLocale()

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: INTL_LOCALE,
  fallbackLocale: 'en',
  messages: { 'zh-TW': zhTW, 'zh-CN': zhCN, en },
})

document.documentElement.lang = { 'zh-TW': 'zh-Hant', 'zh-CN': 'zh-Hans', en: 'en' }[INTL_LOCALE]
