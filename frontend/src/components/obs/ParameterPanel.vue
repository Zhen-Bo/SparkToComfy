<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { LORA_MAX, catalog, dimsKnown, outputDims, selectWorkflow, workflow } from '@/stores/catalog'
import { connection } from '@/stores/connection'
import { locked } from '@/stores/run'
import ObsDropdown from '@/components/obs/ObsDropdown.vue'
import RatioSelector from '@/components/obs/RatioSelector.vue'
import SeedControl from '@/components/obs/SeedControl.vue'
import LoraField from '@/components/obs/LoraField.vue'
import ParamSlider from '@/components/obs/ParamSlider.vue'
import ThemeSwitcher from '@/components/obs/ThemeSwitcher.vue'
import PanelTabs from '@/components/obs/PanelTabs.vue'
import GenerateButton from '@/components/obs/GenerateButton.vue'
import OfflineOverlay from '@/components/obs/OfflineOverlay.vue'
import Textarea from '@/components/ui/Textarea.vue'
import PromptExpandDialog from '@/components/obs/PromptExpandDialog.vue'

// Two parameter tabs: the creative flow in basic and the rarely touched tuning in advanced.
// The advanced options are not collapsed behind a disclosure.
// The tab strip is PanelTabs, shared with the /playground overview.
const { t } = useI18n()
const tab = ref('create')

const workflowItems = computed(() => catalog.workflows.map((w) => ({ value: w.id, label: w.name })))
/* The workflow is locked while generating.
   Switching rebuilds params from the defaults of the new workflow and the size follows, so the viewfinder changes shape, preview frames still arriving at the old ratio get black bars, and the output-size readout no longer describes the job in flight.
   Same as RatioSelector: inert stops a real person, and the handler guards again against a programmatic click. */
const pickWorkflow = (id) => { if (!locked.value) selectWorkflow(id) }

// Control order is the order the backend returns; nothing is reordered.
const shown = computed(() =>
  Object.entries(workflow.value?.parameters?.[tab.value === 'create' ? 'basic' : 'advanced'] ?? {}),
)
// Groups are separated by the edgeline in obs-label::after, so the label rule is the group rule.
// Sections carry no border of their own, which would double up with that rule.
const startsGroup = (i) => i > 0 && shown.value[i][1].type !== shown.value[i - 1][1].type

/** Control names come from i18n.
 * The backend sends no label, so the control key it returns (model, steps and so on) is the i18n key. */
const labelOf = (name) => t(`params.${name}`)

/** Dropdown options are a dictionary: the key is the submitted value and the value is either a label string or {label, disabled?}. */
const itemsOf = (ctl) =>
  Object.entries(ctl.options).map(([value, o]) =>
    typeof o === 'string' ? { value, label: o } : { value, label: o.label, disabled: o.disabled },
  )

const lenOf = (name) => catalog.params[name]?.length ?? 0
// Diff marks after a restore.
// Comparing through stringify covers both the size object and the lora array at once, and params is small enough that nothing cleverer is worth it.
const isDirty = (name) =>
  catalog.restoredBaseline != null &&
  JSON.stringify(catalog.params[name]) !== JSON.stringify(catalog.restoredBaseline[name])
// Only the controls of the current tab are rendered, so a dirty mark on a hidden tab would be invisible: it is lifted onto the tab strip instead.
const groupOf = (tabId) => workflow.value?.parameters?.[tabId === 'create' ? 'basic' : 'advanced'] ?? {}
const dirtyTabs = computed(() =>
  ['create', 'tuning'].filter((id) => Object.keys(groupOf(id)).some(isDirty)),
)

/* Expand editing.
   The panel column is a fixed 267px, 33 characters a line, so a long prompt wraps raggedly however it is broken.
   One dialog serves every multiline field, and expanded says which one is open. */
const expanded = ref(null)
const expandedCtl = computed(() =>
  expanded.value ? { ...groupOf('create'), ...groupOf('tuning') }[expanded.value] : null,
)
// A shared dialog has no radix trigger to return focus to, so it remembers which button opened it.
let opener = null
const openExpand = (name, e) => {
  opener = e.currentTarget
  expanded.value = name
}
watch(expanded, (v) => {
  if (!v) nextTick(() => opener?.focus())
})
const decimalsOf = (ctl) => (ctl.valueKind === 'int' ? 0 : String(ctl.step).split('.')[1]?.length ?? 1)
/** The range readout on the label row.
 * The decimal places follow that control's step, so a 0-7 range never sits next to a CFG of 1.0 in a different format. */
const fmt = (v, ctl) => Number(v ?? 0).toFixed(decimalsOf(ctl))
// The layout contract lives in the declaration: rows arrives with the control from the backend, where it is required for multiline and a missing one fails the boot.
// There is no hidden coupling where raising max_length on negative silently adds two rows.
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
    <PanelTabs v-model="tab" id-base="panel" :dirty="dirtyTabs" :inert="!connection.comfyOnline || null" />

    <div
      class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5 pt-2"
      data-fieldport
      role="tabpanel"
      :id="`panel-tabpanel-${tab}`"
      :aria-labelledby="`panel-tab-${tab}`"
      :inert="!connection.comfyOnline || null"
    >
      <!-- The workflow is not a control but the source of the control declarations, so it always sits first on the basic tab -->
      <section
        v-if="tab === 'create'"
        class="py-2"
        :inert="locked || null"
        :class="locked && 'pointer-events-none opacity-50'"
      >
        <h2 class="obs-label">{{ t('panel.workflow') }}</h2>
        <ObsDropdown :items="workflowItems" :model-value="catalog.workflowId" :label="t('panel.workflow')" @change="pickWorkflow" />
      </section>

      <section
        v-for="([name, ctl], i) in shown"
        :key="name"
        class="py-2"
        :class="startsGroup(i) && 'mt-1 pt-3'"
      >
        <h2 class="obs-label">
          {{ labelOf(name) }}
          <span v-if="ctl.type === 'lora'" class="font-mono text-[11px] tracking-normal text-ink-faint">{{ (catalog.params.lora ?? []).length }}/{{ LORA_MAX }}</span>
          <span
            v-else-if="ctl.type === 'multiline'"
            :id="`count-${name}`"
            class="font-mono text-[11px] tracking-normal tabular-nums"
            :class="lenOf(name) > ctl.maxLength * 0.9 ? 'text-amber-bright' : 'text-ink-faint'"
            translate="no"
          >{{ lenOf(name) }}/{{ ctl.maxLength }}</span>
          <!-- The usable range of a slider, in the same slot and the same type role as the character counter.
               Without it the range can only be discovered by dragging into the ends, which is a red flag for a first-time user -->
          <span
            v-else-if="ctl.type === 'input'"
            class="font-mono text-[11px] tracking-normal tabular-nums text-ink-faint"
            translate="no"
          >{{ fmt(ctl.min, ctl) }}–{{ fmt(ctl.max, ctl) }}</span>
          <span
            v-if="isDirty(name)"
            class="h-1.5 w-1.5 flex-none self-center rounded-full bg-amber"
            role="img"
            :title="t('panel.edited')"
            :aria-label="t('panel.edited')"
          />
          <!-- order-last: the ::after extension rule has order 0, so this pushes the button past it and aligns with the right edge of the field -->
          <button
            v-if="ctl.type === 'multiline'"
            type="button"
            class="obs-tr order-last -my-1.5 flex h-6 w-6 flex-none cursor-pointer items-center justify-center self-center rounded-sm border border-control text-muted-foreground hover:border-amber hover:text-amber active:scale-95"
            :aria-label="t('panel.expand', { field: labelOf(name) })"
            @click="openExpand(name, $event)"
          >
            <svg viewBox="0 0 12 12" class="h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" aria-hidden="true">
              <path d="M7 1h4v4M11 1 6.8 5.2M5 11H1V7M1 11l4.2-4.2" />
            </svg>
          </button>
        </h2>

        <ObsDropdown
          v-if="ctl.type === 'dropdown'"
          :items="itemsOf(ctl)"
          :model-value="catalog.params[name]"
          :label="labelOf(name)"
          @update:model-value="catalog.params[name] = $event"
        />
        <Textarea
          v-else-if="ctl.type === 'multiline'"
          v-model="catalog.params[name]"
          :name="name"
          :rows="ctl.rows"
          :maxlength="ctl.maxLength"
          :fill="name === 'positive'"
          :placeholder="name === 'positive' ? t('params.positiveHint') : undefined"
          :aria-label="labelOf(name)"
          :aria-describedby="`count-${name}`"
          :spellcheck="ctl.spellcheck ?? false"
          translate="no"
        />
        <ParamSlider
          v-else-if="ctl.type === 'input'"
          v-model="catalog.params[name]"
          :min="ctl.min"
          :max="ctl.max"
          :step="ctl.step"
          :decimals="decimalsOf(ctl)"
          :label="labelOf(name)"
        />
        <SeedControl v-else-if="ctl.type === 'seed'" />
        <RatioSelector v-else-if="ctl.type === 'size'" />
        <LoraField v-else-if="ctl.type === 'lora'" />

        <!-- The live region must stay in the DOM with only its text changing; inserted alongside a v-if, a screen reader may not announce it -->
        <span v-if="ctl.type === 'multiline'" class="sr-only" role="status">
          {{ lenOf(name) >= ctl.maxLength ? t('panel.countAtLimit', { max: ctl.maxLength }) : '' }}
        </span>
      </section>
    </div>

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
    <PromptExpandDialog
      :name="expanded"
      :ctl="expandedCtl"
      :label="expanded ? labelOf(expanded) : ''"
      @close="expanded = null"
    />
    </div>
  </aside>
</template>
