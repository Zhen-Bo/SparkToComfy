<script setup>
import { useI18n } from 'vue-i18n'
import { dimsKnown, outputDims } from '@/stores/catalog'
import { connection } from '@/stores/connection'
import ThemeSwitcher from '@/components/obs/ThemeSwitcher.vue'
import ParameterFields from '@/components/obs/ParameterFields.vue'
import GenerateButton from '@/components/obs/GenerateButton.vue'
import OfflineOverlay from '@/components/obs/OfflineOverlay.vue'

const { t } = useI18n()
</script>

<template>
  <aside class="obs-panel flex min-h-0 flex-col border-r border-hairline" :aria-label="t('panel.aria')">
    <div class="border-b border-hairline px-5 pb-3.5 pt-5">
      <div class="flex items-start justify-between gap-3">
        <h1 class="font-disp text-[18px] tracking-[.12em]" translate="no"><span class="text-foreground">Spark</span><span class="text-amber-bright">To</span><span class="text-foreground">Comfy</span></h1>
        <ThemeSwitcher />
      </div>
      <!-- Connection badge, always visible, following connection.comfyOnline.
           Online is the theme amber and offline is the same shape in warning red: both are outline badges and only the hue changes. -->
      <p class="mt-1.5 flex" role="status">
        <span
          class="flex items-center gap-1 rounded-sm border px-1.5 py-px font-sans text-[11px] font-bold tracking-[.12em]"
          :class="connection.comfyOnline ? 'border-amber-dim text-amber' : 'border-destructive/60 text-destructive'"
        >
          <span
            class="inline-block h-1 w-1 rounded-full"
            :class="connection.comfyOnline ? 'bg-amber' : 'animate-pulse bg-destructive'"
            aria-hidden="true"
          />
          {{ t(connection.comfyOnline ? 'offline.badge.online' : 'offline.badge.offline') }}
        </span>
      </p>
    </div>

    <!-- Overlay scope.
         The header and its badge stay reachable and unmasked; the offline overlay covers only this layer, the tab strip, the content and the generate row.
         While the mask is up the three sibling layers are inert: the overlay itself stops the pointer and inert stops Tab and screen readers. -->
    <div class="relative flex min-h-0 flex-1 flex-col">
    <ParameterFields />

    <!-- The generate row at the bottom: the real output size readout plus the main action, pinned rather than scrolled.
         The readout includes the upscale factor (outputDims is the base times upscale) and tracks the factor slider live.
         Orientation, square, portrait or landscape, is already shown by the shape of the stage viewfinder, so there is no badge for it -->
    <div class="border-t border-hairline px-5 pb-4 pt-3" :inert="!connection.comfyOnline || null">
      <div class="mb-2.5 flex items-baseline justify-between font-mono">
        <span class="text-[11px] tracking-[.1em] text-muted-foreground">{{ t('panel.outputSize') }}</span>
        <span class="text-[14px] font-semibold text-amber-bright tabular-nums" translate="no">{{ dimsKnown ? `${outputDims.width} × ${outputDims.height}` : '—' }}</span>
      </div>
      <GenerateButton />
    </div>

    <!-- Offline overlay: it covers this layer whenever comfyOnline is false, whether the engine is down or the backend dropped, and disappears on recovery -->
    <OfflineOverlay />
    </div>
  </aside>
</template>
