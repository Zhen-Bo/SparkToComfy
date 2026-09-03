<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import ParameterPanel from '@/components/obs/ParameterPanel.vue'
import StagePlate from '@/components/obs/StagePlate.vue'
import HistoryRail from '@/components/obs/HistoryRail.vue'
import MobileStudioView from '@/views/MobileStudioView.vue'

// Below 960px the three-column stage is squeezed away, so the phone layout takes over
const MOBILE = matchMedia('(max-width: 959px)')
const mobile = ref(MOBILE.matches)
const onChange = (e) => { mobile.value = e.matches }
onMounted(() => MOBILE.addEventListener('change', onChange))
onBeforeUnmount(() => MOBILE.removeEventListener('change', onChange))
</script>

<template>
  <MobileStudioView v-if="mobile" />

  <!-- First viewport, three columns: parameters on the left, the crosshair viewfinder in the middle with the aspect ratio tracking live, and the collapsible history rail on the right.
       While generating, a progress bar floats at the bottom edge of the stage, absolutely positioned so it never pushes the layout. -->
  <div v-else class="workspace-grid obs-grain grid h-screen" style="grid-template-columns: 364px 1fr auto">
    <ParameterPanel />
    <StagePlate />
    <HistoryRail />
  </div>
</template>
