<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PhTrash } from '@phosphor-icons/vue'
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
import Dialog from '@/components/ui/Dialog.vue'
import PromptExpandDialog from '@/components/obs/PromptExpandDialog.vue'

const { t } = useI18n()
const tab = ref('create')

const workflowItems = computed(() => catalog.workflows.map((w) => ({ value: w.id, label: w.name })))
/* Locked while generating: switching rebuilds the params from the new workflow's defaults mid-run.
   inert stops a real click; the guard catches a programmatic one. */
const pickWorkflow = (id) => { if (!locked.value) selectWorkflow(id) }

const shown = computed(() =>
  Object.entries(workflow.value?.parameters?.[tab.value === 'create' ? 'basic' : 'advanced'] ?? {}),
)
// obs-label::after provides group dividers; avoid adding a second section border.
const startsGroup = (i) => i > 0 && shown.value[i][1].type !== shown.value[i - 1][1].type

// The backend supplies control keys, which also identify their translations.
const labelOf = (name) => t(`params.${name}`)

/** Dropdown options are a dictionary: the key is the submitted value and the value is either a label string or {label, disabled?}. */
const itemsOf = (ctl) =>
  Object.entries(ctl.options).map(([value, o]) =>
    typeof o === 'string' ? { value, label: o } : { value, label: o.label, disabled: o.disabled },
  )

const lenOf = (name) => catalog.params[name]?.length ?? 0
// How the prompts split the scroll area's leftover height.
const FILL = { quality: 0.2, positive: 0.6, negative: 0.2 }
// Params are small JSON values, including nested size and LoRA data, so compare serialized values.
const isDirty = (name) =>
  catalog.restoredBaseline != null &&
  JSON.stringify(catalog.params[name]) !== JSON.stringify(catalog.restoredBaseline[name])
// Surface edits on hidden controls through their tab's dirty mark.
const groupOf = (tabId) => workflow.value?.parameters?.[tabId === 'create' ? 'basic' : 'advanced'] ?? {}
const dirtyTabs = computed(() =>
  ['create', 'tuning'].filter((id) => Object.keys(groupOf(id)).some(isDirty)),
)

const clearLorasOpen = ref(false)
let clearLorasOpener = null
function askClearLoras(event) {
  if (!(catalog.params.lora ?? []).length) return
  clearLorasOpener = event.currentTarget
  clearLorasOpen.value = true
}
watch(clearLorasOpen, (open) => {
  if (!open) nextTick(() => clearLorasOpener?.focus())
})
function confirmClearLoras() {
  catalog.params.lora = []
  clearLorasOpen.value = false
}
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
const fmt = (v, ctl) => Number(v ?? 0).toFixed(decimalsOf(ctl))
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
        <button
          v-if="ctl.type === 'lora'"
          type="button"
          class="obs-tr relative order-last -my-1.5 flex h-6 w-6 flex-none items-center justify-center self-center rounded-sm border border-destructive/60 text-destructive before:absolute before:-inset-2 before:content-[''] hover:bg-destructive/10 active:scale-95 aria-disabled:cursor-not-allowed aria-disabled:opacity-40"
          :aria-label="t('lora.picker.clearAll')"
          :title="t('lora.picker.clearAll')"
          :aria-disabled="!(catalog.params.lora ?? []).length"
          @click="askClearLoras"
        ><PhTrash class="h-[18px] w-[18px]" weight="bold" aria-hidden="true" /></button>
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

  <Dialog :open="clearLorasOpen" max-width="340px" content-class="p-5" @update:open="clearLorasOpen = $event">
    <template #title><h2 class="text-[13.5px] font-bold text-foreground">{{ t('lora.picker.clearTitle') }}</h2></template>
    <template #description><p class="mt-2 text-[12px] leading-relaxed text-muted-foreground">{{ t('lora.picker.clearDescription', { count: (catalog.params.lora ?? []).length }) }}</p></template>
    <div class="mt-4 flex justify-end gap-2">
      <button type="button" class="obs-tr min-h-10 rounded-sm border border-control px-3 text-[12px] text-muted-foreground hover:border-amber hover:text-foreground" @click="clearLorasOpen = false">{{ t('lora.picker.cancel') }}</button>
      <button type="button" class="obs-tr min-h-10 rounded-sm border border-destructive/60 px-3 text-[12px] text-destructive hover:bg-destructive/10" @click="confirmClearLoras">{{ t('lora.picker.clearAll') }}</button>
    </div>
  </Dialog>

  <PromptExpandDialog
    :name="expanded"
    :ctl="expandedCtl"
    :label="expanded ? labelOf(expanded) : ''"
    @close="expanded = null"
  />
</template>
