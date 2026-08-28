import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { initTheme } from './lib/theme'
import { i18n } from './i18n'
// Latin faces.
// Static imports because these are the primary UI faces and the first frame should already be drawn in them;
// the CJK face below is the one that can wait.
import '@fontsource/chakra-petch/400.css'
import '@fontsource/chivo-mono/400.css'
import '@fontsource/chivo-mono/600.css'
import '@fontsource/chivo-mono/700.css'
import './style.css'

initTheme()
createApp(App).use(router).use(i18n).mount('#app')

/*
 * CJK font: Taipei Sans TC, self-hosted because Google Fonts does not carry it.
 * The import is dynamic so the hundreds of @font-face declarations land in a separate CSS chunk injected after mount, instead of in the render-blocking main CSS.
 * The font files themselves are already deferred by unicode-range; it is the declarations that block.
 * The first frame falls back to system-ui, which ships a CJK face on both Windows and macOS, and swaps to Taipei Sans TC right after.
*/
Promise.all([
  import('@vp-tw/taipei-sans-tc/dist/Regular/TaipeiSansTCBeta-Regular.css'),
  import('@vp-tw/taipei-sans-tc/dist/Bold/TaipeiSansTCBeta-Bold.css'),
]).catch((err) => console.error('[fonts] Taipei Sans TC failed to load, falling back to the system font', err))
