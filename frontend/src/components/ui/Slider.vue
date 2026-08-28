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
  ariaLabel: { type: String, default: null },
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
  >
    <!-- A 15px transparent hit band wraps the 3px visual track: radix computes the seek position from the track element, so the padding above and below does not change the value.
         The 14px thumb keeps its size under the WCAG 2.5.8 spacing exception. -->
    <SliderTrack class="relative flex h-[15px] w-full grow items-center">
      <!-- The track stays hairline.
           The title rule is a 2px edgeline, and at equal weight the two lines side by side hide which one can be dragged.
           The amber fill and the thumb carry that affordance instead. -->
      <div class="relative h-[3px] w-full overflow-hidden rounded-full bg-hairline">
        <SliderRange class="absolute h-full bg-amber" />
      </div>
    </SliderTrack>
    <SliderThumb
      class="block h-3.5 w-3.5 rounded-full border-[1.5px] border-amber bg-dome shadow-[0_0_6px_hsl(var(--amber)/.35)] transition-transform hover:scale-110"
      :aria-label="ariaLabel ?? t('common.value')"
    />
  </SliderRoot>
</template>
