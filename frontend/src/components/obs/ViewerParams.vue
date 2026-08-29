<script setup>
/* The parameter panel inside the viewer's left column, collapsed by default and below the key hints.
   The panel keeps a designed set of rows in a designed order and grouping, but each row decides for itself whether it has a value: a missing one is not drawn, so undefined and NaN never reach the screen.
   Declared controls outside those rows are appended at the end, so the panel follows the workflow instead of a hardcoded list.

   Layout:
   - the readings are a <dl> on a two-column grid: the label column takes the widest label in the current locale, the value column is minmax(0,1fr) so it wraps within the panel
   - a value with a break point wraps; an unbroken machine token (a model or LoRA file name) is one line with an ellipsis and its full text in the title, as in LoraField and ObsDropdown
   - each LoRA is one row of name and strength
   - labels are interface type and values are mono with tabular numbers (DESIGN.md: localized text uses the interface font, readings use tabular numbers)
   - the column owns the surface and the width; this component owns its rows and its own scrolling */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { PhCaretDown, PhCaretUp } from '@phosphor-icons/vue'

const { t, te } = useI18n()

const props = defineProps({
  params: { type: Object, required: true },
  shownDims: { type: Object, default: null },
})
const open = defineModel({ type: Boolean, default: false })

const NAMED = ['seed', 'size', 'steps', 'cfg', 'sampler', 'scheduler', 'model', 'lora', 'positive', 'negative', 'quality']
const p = computed(() => props.params)

/* Locale files only carry the control names that exist today.
   A control added to a workflow later has no key, and then the control name itself is shown, so vue-i18n never leaks an internal path such as params.denoise onto the screen. */
const paramLabel = (k) => (te(`params.${k}`) ? t(`params.${k}`) : k)

/* The designed rows, in order, each one drawn only when it has a value.
   The sampler carries its scheduler, because they are read as one setting. */
const readings = computed(() => {
  const v = p.value
  const rows = []
  if (v.seed != null) rows.push({ k: 'seed', label: 'SEED', value: v.seed, lead: true })
  if (v.size) rows.push({ k: 'size', label: t('viewer.size'), value: props.shownDims ? `${props.shownDims.width}×${props.shownDims.height}` : '—' })
  if (v.steps != null) rows.push({ k: 'steps', label: t('viewer.steps'), value: v.steps })
  if (v.cfg != null) rows.push({ k: 'cfg', label: 'CFG', value: Number(v.cfg).toFixed(1) })
  if (v.sampler) rows.push({ k: 'sampler', label: t('viewer.sampler'), value: [v.sampler, v.scheduler].filter(Boolean).join(' ・ ') })
  if (v.model) rows.push({ k: 'model', label: t('viewer.model'), value: v.model, token: true })
  return rows
})
const extras = computed(() =>
  Object.entries(p.value)
    .filter(([k, v]) => !NAMED.includes(k) && v != null && v !== '')
    .map(([k, v]) => ({ k, label: paramLabel(k), value: v })),
)
</script>

<template>
  <div class="flex min-h-0 flex-col">
    <button
      type="button"
      class="flex w-full flex-none items-center justify-between px-4 py-2.5"
      :title="open ? t('viewer.collapsePanel') : t('viewer.expandPanel')"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span class="font-sans text-[13px] font-bold tracking-[.18em] text-foreground">{{ t('viewer.params') }}</span>
      <PhCaretUp v-if="open" class="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      <PhCaretDown v-else class="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
    </button>

    <!-- The list scrolls, so the browser makes it a focus stop for keyboard scrolling; role and label give that stop a name instead of leaving it silent. -->
    <div
      v-if="open"
      class="viewer-params min-h-0 flex-1 overflow-y-auto overscroll-contain border-t border-hairline px-4 py-3 text-[12px] leading-[1.6]"
      tabindex="0"
      role="group"
      :aria-label="t('viewer.params')"
    >
      <dl class="grid grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1">
        <template v-for="r in readings" :key="r.k">
          <dt class="text-muted-foreground">{{ r.label }}</dt>
          <dd
            class="font-mono tabular-nums"
            :class="[r.lead ? 'text-amber-bright' : 'text-foreground', r.token ? 'truncate' : 'break-words']"
            :title="r.token ? r.value : undefined"
            translate="no"
          >{{ r.value }}</dd>
        </template>

        <template v-if="p.lora">
          <dt class="text-muted-foreground">LORA</dt>
          <dd v-if="!p.lora.length" class="font-mono text-foreground">—</dd>
          <dd v-else class="flex flex-col gap-y-1">
            <span v-for="l in p.lora" :key="l.file" class="flex items-baseline justify-between gap-2 font-mono">
              <span class="min-w-0 flex-1 truncate text-foreground" :title="l.file" translate="no">{{ l.file }}</span>
              <span class="flex-none tabular-nums text-muted-foreground" translate="no">×{{ l.strength }}</span>
            </span>
          </dd>
        </template>

        <template v-for="r in extras" :key="r.k">
          <dt class="text-muted-foreground">{{ r.label }}</dt>
          <dd class="break-words font-mono tabular-nums text-foreground" translate="no">{{ r.value }}</dd>
        </template>
      </dl>

      <!-- The prompts are prose, not readings, so they sit below one divider in stacked blocks rather than in the grid.
           The group is conditional, so the divider only appears when there is a prompt under it.
           Viewer chrome never uses ink-faint: it stays below AA over the ghost background on an arbitrary image -->
      <div
        v-if="p.positive || p.quality || p.negative"
        class="mt-3 space-y-2 border-t border-hairline pt-3 leading-[1.7] text-muted-foreground"
      >
        <p v-if="p.positive" class="break-words">
          <i18n-t scope="global" keypath="viewer.positive">
            <template #text><span translate="no">{{ p.positive }}</span></template>
          </i18n-t>
        </p>
        <p v-if="p.quality" class="break-words">
          <i18n-t scope="global" keypath="viewer.quality">
            <template #text><span translate="no">{{ p.quality }}</span></template>
          </i18n-t>
        </p>
        <p v-if="p.negative" class="break-words">
          <i18n-t scope="global" keypath="viewer.negative">
            <template #text><span translate="no">{{ p.negative }}</span></template>
          </i18n-t>
        </p>
      </div>
    </div>
  </div>
</template>
