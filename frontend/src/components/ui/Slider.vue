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
  // Spoken value. radix writes aria-valuenow from the raw number, so "1" is read for a CFG shown as "1.0"; this carries the formatted text instead.
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
  >
    <!-- A 24px transparent hit band wraps the 3px visual track: radix computes the seek position from the track element, so the padding above and below does not change the value.
         24px is the WCAG 2.5.8 minimum. The spacing exception does not cover this control: the readout button sits 12px away, so the 24px circles around the two would overlap. -->
    <SliderTrack class="relative flex h-6 w-full grow items-center">
      <!-- The track stays hairline.
           The title rule is a 2px edgeline, and at equal weight the two lines side by side hide which one can be dragged.
           The amber fill and the thumb carry that affordance instead. -->
      <div class="relative h-[3px] w-full overflow-hidden rounded-full bg-hairline">
        <SliderRange class="absolute h-full bg-amber" />
      </div>
    </SliderTrack>
    <!-- The grip stays 14px, which is the readable instrument size, and an invisible ::after ring extends the pressable area to 24px on every side. -->
    <SliderThumb
      class="relative block h-3.5 w-3.5 rounded-full border-[1.5px] border-amber bg-dome shadow-[0_0_6px_hsl(var(--amber)/.35)] transition-transform after:absolute after:-inset-[5px] after:rounded-full after:content-[''] hover:scale-110"
      :aria-label="ariaLabel ?? t('common.value')"
      :aria-valuetext="ariaValuetext ?? undefined"
    />
  </SliderRoot>
</template>
