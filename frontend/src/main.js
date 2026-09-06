import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { initTheme } from './lib/theme'
import { i18n } from './i18n'
import '@fontsource/chakra-petch/400.css'
import '@fontsource/chivo-mono/400.css'
import '@fontsource/chivo-mono/600.css'
import '@fontsource/chivo-mono/700.css'
import './style.css'

initTheme()
createApp(App).use(router).use(i18n).mount('#app')

/* Defer the large CJK @font-face stylesheet until after mount; unicode-range only defers font files. */
Promise.all([
  import('@vp-tw/taipei-sans-tc/dist/Regular/TaipeiSansTCBeta-Regular.css'),
  import('@vp-tw/taipei-sans-tc/dist/Bold/TaipeiSansTCBeta-Bold.css'),
]).catch((err) => console.error('[fonts] Taipei Sans TC failed to load, falling back to the system font', err))
