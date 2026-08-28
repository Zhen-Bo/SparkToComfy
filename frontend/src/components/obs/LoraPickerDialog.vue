<script setup>
/**
 * The LoRA picker, shared by the workspace and /playground.
 * Opening snapshots the current selection into a scratch list; only confirm writes it back to the store.
*/
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { LORA_MAX, catalog, controls } from '@/stores/catalog'
import { loraCoverUrl } from '@/api/comfy'
import { cn } from '@/lib/utils'
import Dialog from '@/components/ui/Dialog.vue'
import { PhCheck, PhImage } from '@phosphor-icons/vue'

const { t } = useI18n()

const props = defineProps({
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['update:open'])

const ctl = computed(() => controls.value.lora)
const options = computed(() => ctl.value?.options ?? {})
const files = computed(() => Object.keys(options.value))
/* A fixed four-column 960px grid leaves roughly 230px of dead space when fewer LoRAs exist, which reads as a missing card.
   Both the column count and the dialog width follow the real number. */
const cols = computed(() => Math.min(4, Math.max(1, files.value.length)))
const boxWidth = ['', 'max-w-[320px]', 'max-w-[560px]', 'max-w-[760px]', 'max-w-[960px]']

const traySel = ref([]) // scratch selection while the dialog is open; file names, no duplicates
const failed = ref(new Set()) // file names whose cover 404s; the backend always answers not_found

watch(
  () => props.open,
  (v) => {
    if (v) traySel.value = (catalog.params.lora ?? []).map((l) => l.file)
  },
)

function toggle(file) {
  const at = traySel.value.indexOf(file)
  if (at >= 0) traySel.value.splice(at, 1)
  else if (traySel.value.length < LORA_MAX) traySel.value.push(file)
}
function onCoverError(file) {
  failed.value = new Set(failed.value).add(file)
}
function confirm() {
  const prev = new Map((catalog.params.lora ?? []).map((l) => [l.file, l.strength]))
  catalog.params.lora = traySel.value.map((file) => ({
    file,
    strength: prev.get(file) ?? ctl.value.strength.default,
  }))
  emit('update:open', false)
}
</script>

<template>
  <Dialog :open="open" :content-class="`mx-auto p-6 ${boxWidth[cols]}`" @update:open="emit('update:open', $event)">
    <template #title>
      <div class="mb-1 flex items-baseline gap-3.5">
        <h2 class="text-[15px] font-bold tracking-[.18em] text-amber-bright">{{ t('lora.picker.title') }}</h2>
        <span class="text-[11px] tracking-[.12em] text-muted-foreground">{{ t('lora.picker.max', { max: LORA_MAX }) }}</span>
      </div>
    </template>

    <div
      class="mt-4 grid max-h-[58vh] gap-3 overflow-y-auto overscroll-contain p-px"
      :style="{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }"
    >
      <button
        v-for="file in files"
        :key="file"
        type="button"
        :aria-pressed="traySel.includes(file)"
        :disabled="!traySel.includes(file) && traySel.length >= LORA_MAX"
        :class="cn(
          'obs-tr relative overflow-hidden rounded-md border obs-inset text-left',
          traySel.includes(file)
            ? 'border-amber shadow-[0_0_0_1px_hsl(var(--amber))]'
            : 'border-control hover:border-amber',
          !traySel.includes(file) && traySel.length >= LORA_MAX && 'opacity-35',
        )"
        @click="toggle(file)"
      >
        <!-- Fixed 3:4 portrait preview box.
             Cover aspect ratios are unknown, so object-contain leaves margins, the same as the history rail. -->
        <div class="flex aspect-[3/4] items-center justify-center bg-plate-bg">
          <img
            v-if="!failed.has(file)"
            :src="loraCoverUrl(file)"
            :alt="t('lora.cover', { name: options[file] })"
            loading="lazy"
            class="h-full w-full object-contain"
            @error="onCoverError(file)"
          />
          <!-- Placeholder for a 404 cover, so the browser never draws a broken-image icon -->
          <PhImage v-else class="h-8 w-8 text-ink-faint" aria-hidden="true" />
        </div>
        <span
          :class="cn(
            'absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full border-[1.5px] transition-colors',
            traySel.includes(file) ? 'border-amber bg-amber text-primary-foreground' : 'border-edgeline bg-[hsl(var(--dome)/0.7)] text-transparent',
          )"
        ><PhCheck class="h-2.5 w-2.5" aria-hidden="true" /></span>
        <div class="px-2.5 py-2" translate="no">
          <div class="truncate text-[12px] font-bold">{{ options[file] }}</div>
        </div>
      </button>
    </div>

    <div class="mt-4 flex items-center justify-between border-t border-hairline pt-3.5">
      <div>
        <span class="font-mono text-[12px] tracking-wider text-amber-bright">{{ t('lora.picker.selected', { n: traySel.length, max: LORA_MAX }) }}</span>
        <span v-if="traySel.length >= LORA_MAX" class="ml-2.5 text-[11px] text-destructive">{{ t('lora.picker.limit') }}</span>
      </div>
      <button
        type="button"
        class="obs-tr rounded-md border border-amber px-9 py-2.5 font-disp text-[11px] tracking-[.24em] text-amber hover:bg-amber/10 hover:text-amber-bright active:scale-[.98]"
        @click="confirm"
      >{{ t('lora.picker.confirm') }}</button>
    </div>
  </Dialog>
</template>
