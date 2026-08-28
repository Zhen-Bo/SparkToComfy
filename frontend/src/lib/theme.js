/**
 * Theme system: five colorways, the choice is kept in localStorage. ?theme=<id> previews one without saving it, for development and screenshots. --amber is the instrument accent slot that every theme overrides.
*/

export const THEMES = [
  { id: 'amber', nameKey: 'theme.amber', sw: ['#100D0B', '#1F1A15', '#E29C2F'] },
  { id: 'emerald', nameKey: 'theme.emerald', sw: ['#0C0E10', '#1A1F23', '#3CB88A'] },
  { id: 'safelight', nameKey: 'theme.safelight', sw: ['#0D0908', '#241A17', '#E0604C'] },
  { id: 'daylight', nameKey: 'theme.daylight', sw: ['#FBF3EA', '#FFF9F3', '#C1361A'] },
  { id: 'ops', nameKey: 'theme.ops', sw: ['#06080C', '#182231', '#F26E21'] },
]

const KEY = 'deepsky-theme'

/** Ground color of each theme (sw[0]), followed by <meta name="theme-color">. */
function applyThemeColor(id) {
  const hex = THEMES.find((t) => t.id === id)?.sw?.[0]
  if (!hex) return
  let meta = document.querySelector('meta[name="theme-color"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.name = 'theme-color'
    document.head.appendChild(meta)
  }
  meta.content = hex
}

export function initTheme() {
  const q = new URLSearchParams(location.search).get('theme')
  const saved = localStorage.getItem(KEY)
  const id = THEMES.some((t) => t.id === q) ? q : THEMES.some((t) => t.id === saved) ? saved : 'amber'
  document.documentElement.dataset.theme = id
  applyThemeColor(id)
  return id
}

export function setTheme(id) {
  if (!THEMES.some((t) => t.id === id)) return
  document.documentElement.dataset.theme = id
  localStorage.setItem(KEY, id)
  applyThemeColor(id)
}

export function getTheme() {
  return document.documentElement.dataset.theme || 'amber'
}
