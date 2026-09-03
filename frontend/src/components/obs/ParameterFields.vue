<script setup>
/** The tab strip plus every parameter control, shared by the desktop panel and the mobile sheet.
 * Owns the tab state and the prompt expand dialog; the host supplies the header and the generate row. */
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { LORA_MAX, catalog, selectWorkflow, workflow } from '@/stores/catalog'
import { connection } from '@/stores/connection'
import { locked } from '@/stores/run'
import ObsDropdown from '@/components/obs/ObsDropdown.vue'
import RatioSelector from '@/components/obs/RatioSelector.vue'
import SeedControl from '@/components/obs/SeedControl.vue'
import LoraField from '@/components/obs/LoraField.vue'
import ParamSlider from '@/components/obs/ParamSlider.vue'
import PanelTabs from '@/components/obs/PanelTabs.vue'
import Textarea from '@/components/ui/Textarea.vue'
import PromptExpandDialog from '@/components/obs/PromptExpandDialog.vue'

// the tab ids map to the backend's parameter groups: create → basic, tuning → advanced
const { t } = useI18n()
const tab = ref('create')

const workflowItems = computed(() => catalog.workflows.map((w) => ({ value: w.id, label: w.name })))
/* Locked while generating: switching rebuilds the params from the new workflow's defaults mid-run.
   inert stops a real click; the guard catches a programmatic one. */
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
// How the prompts split the scroll area's leftover height.
const FILL = { quality: 0.2, positive: 0.6, negative: 0.2 }
// Diff marks after a restore; stringify covers the size object and the lora array at once, and the params are small.
const isDirty = (name) =>
  catalog.restoredBaseline != null &&
  JSON.stringify(catalog.params[name]) !== JSON.stringify(catalog.restoredBaseline[name])
// Only the controls of the current tab are rendered, so a dirty mark on a hidden tab would be invisible: it is lifted onto the tab strip instead.
const groupOf = (tabId) => workflow.value?.parameters?.[tabId === 'create' ? 'basic' : 'advanced'] ?? {}
const dirtyTabs = computed(() =>
  ['create', 'tuning'].filter((id) => Object.keys(groupOf(id)).some(isDirty)),
)

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
// rows comes from the backend declaration, required for multiline; a missing one fails the boot.
</script>

<template>
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
        <!-- The usable range of a slider, in the same slot and the same type role as the character counter -->
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
          class="obs-tr relative order-last -my-1.5 flex h-6 w-6 flex-none cursor-pointer items-center justify-center self-center rounded-sm border border-control text-muted-foreground before:absolute before:-inset-2 before:content-[''] hover:border-amber hover:text-amber active:scale-95"
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
        :fill="FILL[name] ?? 0"
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

  <PromptExpandDialog
    :name="expanded"
    :ctl="expandedCtl"
    :label="expanded ? labelOf(expanded) : ''"
    @close="expanded = null"
  />
</template>
