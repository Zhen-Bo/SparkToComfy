/* Apple keyboards generate with Command+Enter, everything else with Control+Enter. */
const isApple = typeof navigator !== 'undefined'
  && /mac|iphone|ipad|ipod/i.test(navigator.userAgentData?.platform ?? navigator.platform ?? '')

export const MOD_KEY = isApple
  ? { label: '⌘', aria: 'Meta+Enter' }
  : { label: 'Ctrl', aria: 'Control+Enter' }

/** Either modifier works on every platform, so a Windows keyboard on a Mac is not locked out. */
export const isGenerateShortcut = (e) =>
  e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && !e.repeat && !e.isComposing
