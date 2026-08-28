<script setup>
/**
 * The basic/advanced tab strip.
 * The workspace parameter panel and the /playground overview share this one implementation, so a change here reaches both.
*/
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { cn } from '@/lib/utils'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: String, required: true },
  // aria id prefix: id and aria-controls must match the host panel tabpanel id
  idBase: { type: String, default: 'panel' },
  // Ids of edited tabs.
  // A hidden tab can only show its dirty mark through this. /playground passes nothing, so it defaults to empty.
  dirty: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const tabs = [
  { id: 'create', key: 'tabs.create' },
  { id: 'tuning', key: 'tabs.tuning' },
]

/** Arrow-key navigation for the tablist (WAI): left/right moves focus and selects. */
const tabRefs = ref([])
function onTabKeydown(e, i) {
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
  e.preventDefault()
  const d = e.key === 'ArrowRight' ? 1 : -1
  const next = (i + d + tabs.length) % tabs.length
  emit('update:modelValue', tabs[next].id)
  tabRefs.value[next]?.focus()
}
</script>

<template>
  <div class="flex border-b border-hairline" role="tablist" :aria-label="t('tabs.aria')">
    <button
      v-for="(tab, i) in tabs"
      :key="tab.id"
      :ref="(el) => (tabRefs[i] = el)"
      type="button"
      role="tab"
      :id="`${idBase}-tab-${tab.id}`"
      :aria-selected="modelValue === tab.id"
      :aria-controls="`${idBase}-tabpanel-${tab.id}`"
      :tabindex="modelValue === tab.id ? 0 : -1"
      :class="cn(
        'obs-tr flex flex-1 items-baseline justify-center gap-2 py-2.5',
        modelValue === tab.id
          ? 'text-amber-bright shadow-[inset_0_-2px_0_hsl(var(--amber))]'
          : 'text-muted-foreground hover:text-foreground',
      )"
      @click="emit('update:modelValue', tab.id)"
      @keydown="onTabKeydown($event, i)"
    >
      <span class="text-[15px] font-bold tracking-[.18em]">{{ t(tab.key) }}</span>
      <span
        v-if="dirty.includes(tab.id)"
        class="h-1 w-1 flex-none self-center rounded-full bg-amber"
        role="img"
        :aria-label="t('panel.edited')"
      />
    </button>
  </div>
</template>
