<script setup>
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Slider from '@/components/ui/Slider.vue'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: Number, required: true },
  min: { type: Number, default: 0 },
  max: { type: Number, default: 100 },
  step: { type: Number, default: 1 },
  decimals: { type: Number, default: 0 },
  label: { type: String, default: null }, // accessible name, shared by the slider and the input
})
const labelText = computed(() => props.label ?? t('common.value'))
const emit = defineEmits(['update:modelValue'])

const inner = computed({
  get: () => [props.modelValue],
  set: (v) => emit('update:modelValue', v[0]),
})

const editing = ref(false)
const draft = ref('')
const inputEl = ref(null)

// Focus after each input mount so repeated edits do not depend on native autofocus.
function startEdit() {
  draft.value = props.modelValue.toFixed(props.decimals)
  editing.value = true
  nextTick(() => {
    inputEl.value?.focus()
    inputEl.value?.select()
  })
}
// A blur-driven exit must not pull focus back from the control the user just clicked.
const readoutEl = ref(null)
function leaveEdit(refocus) {
  editing.value = false
  if (refocus) nextTick(() => readoutEl.value?.focus())
}
function commit(refocus = false) {
  let v = parseFloat(draft.value)
  if (!Number.isNaN(v)) {
    v = Math.min(props.max, Math.max(props.min, v))
    v = Math.round(v / props.step) * props.step
    emit('update:modelValue', +v.toFixed(props.decimals))
  }
  leaveEdit(refocus)
}
function onKey(e) {
  if (e.key === 'Enter') commit(true)
  if (e.key === 'Escape') leaveEdit(true)
}
</script>

<template>
  <div>
    <div class="flex items-center gap-3">
      <Slider v-model="inner" :min="min" :max="max" :step="step" class="flex-1" :aria-label="labelText" :aria-valuetext="modelValue.toFixed(decimals)" />
      <input
        v-if="editing"
        ref="inputEl"
        v-model="draft"
        type="text"
        inputmode="decimal"
        :aria-label="t('slider.directInput', { label: labelText })"
        class="h-8 w-[52px] flex-none rounded-sm border border-amber bg-dome px-1 text-center font-mono text-[13.5px] font-semibold text-amber-bright tabular-nums"
        @blur="commit(false)"
        @keydown="onKey"
      />
      <!-- Match the input dimensions to prevent a layout shift when editing starts. -->
      <button
        v-else
        ref="readoutEl"
        type="button"
        :title="t('slider.clickToInput')"
        :aria-label="t('slider.readout', { label: labelText, value: modelValue.toFixed(decimals) })"
        class="obs-tr flex h-8 w-[52px] flex-none items-center justify-center rounded-sm border border-control px-1 text-center font-mono text-[13.5px] font-semibold text-amber-bright tabular-nums hover:border-amber hover:bg-amber/10"
        @click="startEdit"
      >{{ modelValue.toFixed(decimals) }}</button>
    </div>
  </div>
</template>
