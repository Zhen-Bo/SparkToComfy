<script setup>
/** The phone layout; StudioView mounts it below 960px. */
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { connection } from '@/stores/connection'
import { history } from '@/stores/history'
import { dimsKnown, outputDims } from '@/stores/catalog'
import { notify } from '@/stores/notify'
import StagePlate from '@/components/obs/StagePlate.vue'
import MobileSheet from '@/components/obs/MobileSheet.vue'
import GenerateButton from '@/components/obs/GenerateButton.vue'
import HistoryViewer from '@/components/obs/HistoryViewer.vue'
import { PhClockCounterClockwise } from '@phosphor-icons/vue'

const { t } = useI18n()

// the viewer has no empty state, so an empty history gets a toast instead
const viewing = ref(false)
const historyBtn = ref(null)
function openHistory() {
  if (!history.entries.length) return notify(t('history.empty'))
  viewing.value = true
}
function closeViewer() {
  viewing.value = false
  nextTick(() => historyBtn.value?.focus())
}

const sheetRef = ref(null)
const sheetOpen = ref(false)
function onStageTap(e) {
  const s = sheetRef.value
  if (!s?.expanded || s.el?.contains(e.target)) return
  s.collapse()
}
</script>

<template>
  <div class="obs-grain flex h-dvh flex-col overflow-hidden">
    <!-- chrome is plate; deep black is the preview area only -->
    <header class="obs-panel flex flex-none items-center justify-between gap-3 border-b border-hairline px-4 py-[21px]">
      <h1 class="font-disp text-[18px] tracking-[.12em]" translate="no"><span class="text-foreground">Spark</span><span class="text-amber-bright">To</span><span class="text-foreground">Comfy</span></h1>
      <p role="status">
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
    </header>

    <!-- The bottom padding keeps the stage's status bars above the collapsed strip; overflow-hidden clips the collapsed sheet off the generate row -->
    <div class="relative min-h-0 flex-1 overflow-hidden pb-[22px]" @click="onStageTap">
      <StagePlate class="h-full" compact />
      <div
        class="pointer-events-none absolute inset-0 z-20 backdrop-blur-sm transition-opacity duration-300"
        :class="sheetOpen ? 'opacity-100' : 'opacity-0'"
        :style="{ background: 'hsl(var(--overlay) / 0.35)' }"
        aria-hidden="true"
      />
      <MobileSheet ref="sheetRef" v-model:expanded="sheetOpen" />
    </div>

    <!-- The output-size readout is pinned here instead of riding the sheet's strip, so opening the drawer never carries it upward -->
    <footer class="obs-panel flex-none px-4 pb-[max(12px,env(safe-area-inset-bottom))] pt-2.5">
      <p class="mb-2 flex items-baseline justify-between">
        <span class="text-[11px] tracking-[.1em] text-muted-foreground">{{ t('panel.outputSize') }}</span>
        <span class="font-mono text-[14px] font-semibold text-amber-bright tabular-nums" translate="no">{{ dimsKnown ? `${outputDims.width} × ${outputDims.height}` : '—' }}</span>
      </p>
      <div class="flex items-stretch gap-2.5">
        <!-- Offline inert wraps only the main action: browsing past results does not need Comfy. min-h-12 keeps the row at the 48px touch target. -->
        <div class="min-h-12 flex-1" :inert="!connection.comfyOnline || null">
          <GenerateButton class="h-full w-full" />
        </div>
        <button
          ref="historyBtn"
          type="button"
          :aria-label="t('history.title')"
          :title="t('history.title')"
          class="obs-tr grid w-12 flex-none cursor-pointer place-items-center rounded-sm border border-control text-muted-foreground hover:border-amber hover:text-amber active:scale-95"
          @click="openHistory"
        >
          <PhClockCounterClockwise class="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
    </footer>

    <HistoryViewer v-if="viewing" :entries="history.entries" :start-index="0" @close="closeViewer" />
  </div>
</template>
