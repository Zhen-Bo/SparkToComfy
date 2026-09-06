<script setup>
import { cn } from '@/lib/utils'
import { useI18n } from 'vue-i18n'
import { SliderRange, SliderRoot, SliderThumb, SliderTrack } from 'radix-vue'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: Array, required: true },
  min: { type: Number, default: 0 },
  max: { type: Number, default: 100 },
  step: { type: Number, default: 1 },
  class: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  ariaLabel: { type: String, default: null },
  // Match the displayed formatting (e.g. CFG 1.0) instead of announcing only the raw number.
  ariaValuetext: { type: String, default: null },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <SliderRoot
    :class="cn('relative flex w-full touch-none select-none items-center', props.class)"
    :model-value="props.modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :min="min"
    :max="max"
    :step="step"
    :disabled="disabled"
  >
    <!-- Enlarge the hit area vertically without changing the horizontal value mapping. -->
    <SliderTrack class="relative flex h-6 w-full grow items-center">
      <div class="relative h-[3px] w-full overflow-hidden rounded-full bg-hairline">
        <SliderRange class="absolute h-full bg-amber" />
      </div>
    </SliderTrack>
    <!-- The pseudo-element expands the 14px thumb to a 24px hit target. -->
    <SliderThumb
      class="relative block h-3.5 w-3.5 rounded-full border-[1.5px] border-amber bg-dome shadow-[0_0_6px_hsl(var(--amber)/.35)] transition-transform after:absolute after:-inset-[5px] after:rounded-full after:content-[''] hover:scale-110"
      :aria-label="ariaLabel ?? t('common.value')"
      :aria-valuetext="ariaValuetext ?? undefined"
    />
  </SliderRoot>
</template>
