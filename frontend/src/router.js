import { createRouter, createWebHistory } from 'vue-router'
import StudioView from '@/views/StudioView.vue'
import { i18n } from '@/i18n'

/**
 * Routes, history mode. / workspace: the three observatory columns /playground component overview: the real components from src/components, one source Any unknown path falls back to the workspace.
*/
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'studio',
      component: StudioView,
      meta: { titleKey: 'app.titleStudio' },
    },
    {
      path: '/playground',
      name: 'playground',
      // Split on demand so the tooling page does not weigh on the workspace first paint
      component: () => import('@/views/MatrixView.vue'),
      meta: { titleKey: 'app.titlePlayground' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.afterEach((to) => {
  if (to.meta?.titleKey) document.title = i18n.global.t(to.meta.titleKey)
})
