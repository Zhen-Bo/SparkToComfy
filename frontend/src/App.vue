<script setup>
import { onMounted } from 'vue'
import { initStudio } from '@/stores/connection'
import { toast } from '@/stores/notify'

// Toast transition classes are in the style block below.
// from/to carry translateX(-50%) explicitly, so they do not depend on how Tailwind orders its centring transforms.

onMounted(initStudio)
</script>

<template>
  <!--
    DIRECTION CONTRACT - Deep-Sky Observatory Console
    THESIS: a night-vision observatory console; the interface is the instrument.
    It refuses the purple-on-black AI panel that the category defaults to.
    OWN-WORLD: deep blue-black sky with amber instrument light, the way real night vision protects dark adaptation.
    Chakra Petch for brand text, Chivo Mono for readouts (a slashless zero), thin hairlines and corner brackets.
    Interface text is translated (zh-TW, zh-CN, en) and follows the browser, in src/i18n/locales/.
    STORY: the observatory metaphor stays in the visual layer, the star field and the crosshair.
    Every piece of operating text uses plain words.
    ROUTES: / is the three-column workspace, /playground the component overview that mounts the real components from src/components, so one change reaches both.
    -->
  <router-view />

  <!-- Global toast: top centre, gone on its own after about 2.2 seconds.
       It is teleported to body for two reasons.
       The viewer and the clear dialog set #app inert, and a role=status left inside #app would leave the accessibility tree and never be announced.
       And at the bottom it would sit right on the viewer navigation dock.
       Top centre is empty on both screens. -->
  <Teleport to="body">
    <Transition name="toast">
      <div
        v-if="toast.notice"
        class="obs-panel fixed left-1/2 top-7 z-[300] -translate-x-1/2 border border-amber/50 px-4 py-2 font-mono text-[11px] tracking-[.12em] text-amber-bright shadow-[0_4px_16px_hsl(var(--dome)/.5)]"
        role="status"
      >{{ toast.notice }}</div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* The toast enters from 8px above over 200ms and leaves upward by 4px over 160ms.
   The direction follows its position: it always arrives from the nearer screen edge. */
.toast-enter-active { transition: opacity .2s var(--ease-fluid), transform .2s var(--ease-fluid); }
.toast-leave-active { transition: opacity .16s ease-in, transform .16s ease-in; }
.toast-enter-from  { opacity: 0; transform: translate(-50%, -8px); }
.toast-leave-to    { opacity: 0; transform: translate(-50%, -4px); }
</style>
