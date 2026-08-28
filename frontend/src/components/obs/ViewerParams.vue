<script setup>
/* The parameter panel at the top left of the viewer overlay, collapsed by default and below the fixed caption row.
   The panel keeps a designed set of rows in a designed order and grouping, but each row decides for itself whether it has a value: a missing one is not drawn, so undefined and NaN never reach the screen.
   Declared controls outside those rows are appended at the end, so the panel follows the workflow instead of a hardcoded list. */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PhCaretDown, PhCaretUp } from '@phosphor-icons/vue'

const { t, te } = useI18n()

const props = defineProps({
  params: { type: Object, required: true },
  shownDims: { type: Object, default: null },
})
const open = defineModel({ type: Boolean, default: false })

const NAMED = ['seed', 'size', 'steps', 'cfg', 'sampler', 'scheduler', 'model', 'lora', 'positive', 'negative', 'quality']
const extras = computed(() =>
  Object.entries(props.params).filter(([k, v]) => !NAMED.includes(k) && v != null && v !== ''),
)
/* Locale files only carry the control names that exist today.
   A control added to a workflow later has no key, and then the control name itself is shown, so vue-i18n never leaks an internal path such as params.denoise onto the screen. */
const paramLabel = (k) => (te(`params.${k}`) ? t(`params.${k}`) : k)

const p = computed(() => props.params)
const panel = ref(null)
</script>

<template>
  <div ref="panel" class="obs-ghost pointer-events-auto w-[264px] flex-none border border-hairline">
    <button
      type="button"
      class="flex w-full items-center justify-between px-4 py-2.5"
      :title="open ? t('viewer.collapsePanel') : t('viewer.expandPanel')"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span class="font-sans text-[13px] font-bold tracking-[.18em] text-foreground">{{ t('viewer.params') }}</span>
      <PhCaretUp v-if="open" class="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      <PhCaretDown v-else class="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
    </button>
    <div v-if="open" class="viewer-params max-h-[calc(100vh-190px)] overflow-y-auto overscroll-contain border-t border-hairline px-4 py-3">
      <div class="font-mono text-[12px] leading-[2] text-muted-foreground">
        <template v-if="p.seed != null">SEED <span class="text-amber-bright" translate="no">{{ p.seed }}</span><br></template>
        <template v-if="p.size">{{ t('viewer.size') }} <span class="text-foreground" translate="no">{{ shownDims ? `${shownDims.width}×${shownDims.height}` : '—' }}</span><br></template>
        <template v-if="p.steps != null">{{ t('viewer.steps') }} <span class="text-foreground" translate="no">{{ p.steps }}</span></template>
        <template v-if="p.cfg != null"> ・ CFG <span class="text-foreground" translate="no">{{ Number(p.cfg).toFixed(1) }}</span></template>
        <br v-if="p.steps != null || p.cfg != null">
        <template v-if="p.sampler">{{ t('viewer.sampler') }} <span class="text-foreground" translate="no">{{ [p.sampler, p.scheduler].filter(Boolean).join(' ・ ') }}</span><br></template>
        <template v-if="p.model">{{ t('viewer.model') }} <span class="text-foreground" translate="no">{{ p.model }}</span><br></template>
        <template v-if="p.lora">LORA <span class="text-foreground" translate="no">{{ p.lora.length ? p.lora.map((l) => `${l.file} ×${l.strength}`).join(' ｜ ') : '—' }}</span><br></template>
        <template v-for="[k, v] in extras" :key="k">{{ paramLabel(k) }} <span class="text-foreground" translate="no">{{ v }}</span><br></template>
      </div>
      <div class="mt-2 border-t border-hairline pt-2 text-[12px] leading-[1.7] text-muted-foreground" translate="no">{{ p.positive }}</div>
      <!-- Viewer chrome never uses ink-faint: it stays below AA over the 88% ghost background on an arbitrary image -->
      <div v-if="p.quality" class="mt-1 text-[12px] leading-[1.7] text-muted-foreground">
        <i18n-t scope="global" keypath="viewer.quality">
          <template #text><span translate="no">{{ p.quality }}</span></template>
        </i18n-t>
      </div>
      <div v-if="p.negative" class="mt-1 text-[12px] leading-[1.7] text-muted-foreground">
        <i18n-t scope="global" keypath="viewer.negative">
          <template #text><span translate="no">{{ p.negative }}</span></template>
        </i18n-t>
      </div>
    </div>
  </div>
</template>
