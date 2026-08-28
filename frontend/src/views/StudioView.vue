<script setup>
import { useI18n } from 'vue-i18n'
import ParameterPanel from '@/components/obs/ParameterPanel.vue'
import StagePlate from '@/components/obs/StagePlate.vue'
import HistoryRail from '@/components/obs/HistoryRail.vue'

const { t } = useI18n()
</script>

<template>
  <!-- First viewport, three columns: parameters on the left, the crosshair viewfinder in the middle with the aspect ratio tracking live, and the collapsible history rail on the right.
       While generating, a progress bar floats at the bottom edge of the stage, absolutely positioned so it never pushes the layout. -->
  <div class="workspace-grid obs-grain grid h-screen" style="grid-template-columns: 364px 1fr auto">
    <ParameterPanel />
    <StagePlate />
    <HistoryRail />
  </div>

  <!-- Narrow viewport guard.
       This is a desktop-density product, and below 960px the stage gets squeezed, so it shows a notice at the top rather than trying to reflow. -->
  <div class="minw-note" role="status">{{ t('app.minwNote') }}</div>
</template>

<style scoped>
.minw-note {
  display: none;
  position: fixed;
  inset: 0 0 auto;
  z-index: 400;
  padding: 4px 12px;
  /* A solid inset background keeps contrast at 6.8:1 or better in every theme.
     The amber-dim rule along the bottom edge carries the warning identity instead. */
  background: hsl(var(--inset));
  border-bottom: 1px solid hsl(var(--amber-dim));
  color: hsl(var(--amber-bright));
  font-family: 'Taipei Sans TC', sans-serif;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: .08em;
  text-align: center;
}
/* The notice bar is fixed and takes no space of its own, so its 26px would cover the left column header: the brand text and the theme switcher.
   While it shows, the whole grid is pushed down by the same height. box-sizing is border-box everywhere, so h-screen shrinks instead of overflowing. */
@media (max-width: 959px) {
  .minw-note { display: block; }
  .workspace-grid { padding-top: 27px; }
}
</style>
