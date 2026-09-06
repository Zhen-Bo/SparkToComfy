<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalog, currentDims, outputDims } from '@/stores/catalog'
import { dismissOutcome, queueEta, retryLastRun, run } from '@/stores/run'
import QueueSlots from '@/components/obs/QueueSlots.vue'
import { PhX } from '@phosphor-icons/vue'

const { t } = useI18n()

const props = defineProps({ compact: { type: Boolean, default: false } })

const stars = ref('')

const stage = ref(null)
const avail = ref({ w: 0, h: 0 })
let ro = null

onMounted(() => {
  // A fixed pseudo-random star field: it never twinkles and never reshuffles
  let r = 991
  const rnd = () => ((r = (r * 16807) % 2147483647) / 2147483647)
  let s = ''
  for (let i = 0; i < 90; i++) {
    s += `<circle cx="${(rnd() * 100).toFixed(1)}" cy="${(rnd() * 100).toFixed(1)}" r="${(0.05 + rnd() * 0.09).toFixed(2)}" fill="currentColor" opacity="${(0.15 + rnd() * 0.5).toFixed(2)}"/>`
  }
  stars.value = s

    ro = new ResizeObserver(([entry]) => {
    avail.value = { w: entry.contentRect.width, h: entry.contentRect.height }
  })
  ro.observe(stage.value)
})
/* Animate dimension changes without animating every window resize or the initial 0x0 measurement.
   Remove the class after the 300ms transition plus a 50ms margin. */
const animateShape = ref(false)
let shapeTimer = 0
watch(
  () => `${currentDims.value.width}x${currentDims.value.height}`,
  () => {
    animateShape.value = true
    clearTimeout(shapeTimer)
    shapeTimer = setTimeout(() => { animateShape.value = false }, 350)
  },
)
onUnmounted(() => {
  ro?.disconnect()
  clearTimeout(shapeTimer)
})

// Fit inside the available space while preserving the image ratio.
const frameStyle = computed(() => {
  const { width, height } = currentDims.value
  const { w, h } = avail.value
  if (!w || !h) return { width: '0px', height: '0px' }
  const sc = Math.min(w / width, h / height)
  return { width: `${Math.round(width * sc)}px`, height: `${Math.round(height * sc)}px` }
})

const progressPct = computed(() =>
  run.progress ? Math.round((run.progress.step / run.progress.total) * 100) : 0,
)
// Reserve the total's digit width to avoid shifts as the step count grows.
const stepDigits = computed(() => String(run.progress?.total ?? 0).length)

const SCAN = new Set(['upscaling', 'transfer'])

const scanning = computed(() => SCAN.has(run.phase))
const upscaling = computed(() => run.phase !== 'transfer' && Number(catalog.params.upscale) > 1)
const scanLabel = computed(() =>
  run.phase === 'transfer'
    ? t('stage.transfer')
    : upscaling.value
      ? t('stage.upscaling')
      : t('stage.outputting'),
)
const upscaleLabel = computed(() => `×${Number(catalog.params.upscale ?? 1).toFixed(1)}`)

const finalOn = computed(() => Boolean(run.currentImage))
const previewOn = computed(() => Boolean(run.previewFrame) && !finalOn.value)

const queueOn = computed(() => run.phase === 'queued' || run.phase === 'preparing')

const outcome = computed(() => (run.busy ? null : run.lastOutcome))
const outcomeText = computed(() =>
  outcome.value?.kind === 'error'
    ? t('stage.failed', { reason: outcome.value.reason })
    : t('stage.cancelled'),
)

// Clear the live region between runs so repeated completions can be announced.
const doneNote = ref('')
watch(
  () => run.phase,
  (p, prev) => {
    if (p === 'queued' || p === 'preparing') doneNote.value = ''
    else if (p === 'idle' && SCAN.has(prev) && run.currentImage)
      doneNote.value = t('stage.done')
  },
)
</script>

<template>
  <main class="relative flex min-h-0 flex-col overflow-hidden bg-dome">
    <svg class="pointer-events-none absolute inset-0 h-full w-full text-foreground" :style="{ opacity: 'var(--stars-opacity)' }" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" v-html="stars" />
    <div class="pointer-events-none absolute inset-0" style="background: radial-gradient(1000px 640px at 50% 42%, hsl(var(--glow) / .06) 0%, transparent 70%)" />

    <div ref="stage" class="relative z-10 flex min-h-0 w-full flex-1 items-center justify-center" :class="props.compact ? 'p-4' : 'p-8'">
    <div
      class="obs-corners relative"
      :class="animateShape && 'transition-[width,height] duration-300 ease-out'"
      :style="frameStyle"
    >
      <div
        class="absolute inset-0 rounded-[3px] border border-hairline p-[6px]"
        style="background: linear-gradient(180deg, hsl(var(--elevated)), color-mix(in srgb, hsl(var(--elevated)) 88%, black)); box-shadow: inset 0 1px 0 hsl(0 0% 100% / .05)"
      >
        <div class="relative h-full w-full overflow-hidden border border-hairline bg-plate-bg">
          <img
            v-if="finalOn"
            :key="run.currentImage"
            :src="run.currentImage"
            class="art-enter h-full w-full object-contain"
            :alt="t('stage.resultAlt', { width: outputDims.width, height: outputDims.height })"
          />
          <!-- Preview frames: each replaces the previous one with no entry animation, which would flicker at several frames a second -->
          <img
            v-else-if="previewOn"
            :src="run.previewFrame"
            class="h-full w-full object-contain"
            :alt="t('stage.previewAlt')"
          />
          <div class="sr-only" role="status">{{ doneNote }}</div>

          <div v-if="queueOn" class="qs-ovl absolute inset-0 z-10 flex items-center justify-center">
            <QueueSlots :ahead="run.queueAhead ?? 0" :ready="run.phase === 'preparing'" :eta="queueEta" />
          </div>

          <!-- Share this node across upscaling and transfer so the animation does not restart. -->
          <div v-if="scanning" class="upscan" aria-hidden="true">
            <i class="upscan-line" />
          </div>
        </div>
      </div>

      <div v-if="!finalOn && !previewOn" class="pointer-events-none absolute inset-0 z-10" aria-hidden="true">
        <div class="absolute -bottom-3.5 -top-3.5 left-1/2 w-px" style="background: linear-gradient(to bottom, transparent, hsl(var(--amber) / .35) 30%, hsl(var(--amber) / .35) 70%, transparent)" />
        <div class="absolute -left-3.5 -right-3.5 top-1/2 h-px" style="background: linear-gradient(to right, transparent, hsl(var(--amber) / .35) 30%, hsl(var(--amber) / .35) 70%, transparent)" />
      </div>
    </div>
    </div>

    <div
      v-if="run.busy && run.progress && !scanning"
      role="progressbar"
      :aria-valuenow="progressPct"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="t('stage.progressAria')"
      class="absolute inset-x-0 bottom-0 z-20 flex h-7 items-center gap-3 border-t border-hairline bg-[hsl(var(--inset))]/85 px-4 upsbar"
    >
      <div class="relative h-[3px] flex-1 overflow-hidden bg-amber/20" aria-hidden="true">
        <div class="absolute inset-y-0 left-0 w-full origin-left bg-amber shadow-[0_0_10px_hsl(var(--amber)/.8)] transition-transform duration-100" :style="{ transform: `scaleX(${progressPct / 100})` }" />
      </div>
      <div class="shrink-0 font-mono text-[11px] font-bold tracking-[.14em] text-amber-bright tabular-nums">
        {{ String(progressPct).padStart(3, '0') }}% ・ {{ t('stage.step', { step: String(run.progress.step).padStart(stepDigits, '0'), total: run.progress.total }) }}
      </div>
    </div>
    <div
      v-if="scanning"
      role="status"
      :aria-label="scanLabel"
      class="absolute inset-x-0 bottom-0 z-20 flex h-7 items-center justify-center gap-3 border-t border-hairline bg-[hsl(var(--inset))]/85 upsbar"
    >
      <span class="font-sans text-[11px] font-bold tracking-[.14em] text-amber-bright">{{ scanLabel }}</span>
      <span v-if="upscaling" class="font-mono text-[11px] font-bold text-amber-bright tabular-nums" translate="no">{{ upscaleLabel }}</span>
    </div>
    <div
      v-if="outcome"
      :role="outcome.kind === 'error' ? 'alert' : 'status'"
      class="absolute inset-x-0 bottom-0 z-20 flex h-7 items-center gap-2 border-t bg-[hsl(var(--inset))]/85 pl-4 pr-1.5 upsbar"
      :class="outcome.kind === 'error' ? 'border-destructive/70' : 'border-hairline'"
    >
      <span
        class="min-w-0 flex-1 truncate font-sans text-[11px] font-bold tracking-[.14em]"
        :class="outcome.kind === 'error' ? 'text-destructive' : 'text-muted-foreground'"
        :title="outcomeText"
      >{{ outcomeText }}</span>
      <button
        v-if="outcome.kind === 'error'"
        type="button"
        class="obs-tr h-6 shrink-0 cursor-pointer rounded-sm border border-control px-2.5 font-sans text-[11px] font-bold tracking-[.14em] text-foreground hover:border-amber hover:text-amber active:scale-95"
        :aria-label="t('stage.retryAria')"
        @click="retryLastRun"
      >{{ t('stage.retry') }}</button>
      <button
        type="button"
        class="obs-tr grid h-6 w-6 shrink-0 cursor-pointer place-items-center rounded-sm text-muted-foreground hover:bg-elevated hover:text-foreground active:scale-95"
        :aria-label="t('stage.dismiss')"
        @click="dismissOutcome"
      >
        <PhX class="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  </main>
</template>

<style scoped>
.qs-ovl { animation: qsOvlIn .25s var(--ease-fluid) both; }
@keyframes qsOvlIn { from { opacity: 0; } to { opacity: 1; } }

/* Indeterminate activity indicator; its position does not represent progress. */
.upscan { position: absolute; inset: 0; z-index: 10; overflow: hidden; pointer-events: none; }
.upscan-line { position: absolute; inset: 0;
  background: linear-gradient(to right, transparent 0, hsl(var(--amber-bright) / .14) 16px, hsl(var(--amber-bright)) 16px, hsl(var(--amber-bright)) 18px, transparent 18px) no-repeat;
  filter: drop-shadow(0 0 4px hsl(var(--amber) / .6));
  animation: upScan 2.4s var(--ease-fluid) infinite; }
@keyframes upScan {
  0% { transform: translateX(-24px); opacity: 0; }
  8% { opacity: 1; }
  90% { opacity: 1; }
  100% { transform: translateX(100%); opacity: 0; }
}

.upsbar { animation: upsBarIn .3s var(--ease-fluid) both; }
@keyframes upsBarIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

.art-enter { animation: artIn .26s var(--ease-fluid) both; }
@keyframes artIn {
  from { opacity: 0; transform: scale(.97); }
  to   { opacity: 1; transform: scale(1); }
}
</style>
