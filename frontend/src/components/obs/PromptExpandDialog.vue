<script setup>
/**
 * Enlarged prompt editing.
 *
 * The panel column is 267px, which at 12px monospace fits 33 characters per line, while a single tag runs 10 to 20 characters.
 * Every wrap therefore looks ragged, and a hyphenated tag such as `ultra-detailed` breaks across two lines.
 * No CSS stops a hyphen break inside a <textarea>: word-break, text-wrap, line-break and hyphens all produce identical output.
 * Column width is the only variable, so this dialog widens it to roughly 80 characters and there is simply less wrapping.
 *
 * It writes catalog.params[name] directly with no draft state, because the flow is fill in and submit.
 * Undo is covered by the dirty marks on a restored run.
*/
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalog } from '@/stores/catalog'
import Dialog from '@/components/ui/Dialog.vue'
import Textarea from '@/components/ui/Textarea.vue'

const props = defineProps({
  // Name of the control being expanded; null means closed.
  name: { type: String, default: null },
  ctl: { type: Object, default: null },
  label: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const { t } = useI18n()

/* radix Presence waits for the exit animation before unmounting (see the note in ui/Dialog.vue), but name and ctl are already null the moment it closes.
   Reading ctl.maxLength would throw a TypeError during the exit, and a failed render stalls the close, leaving the overlay stuck open.
   So the last values are kept for those exit frames; whether it is open still depends only on the props. */
const last = ref({ name: null, ctl: null, label: '' })
watch(
  () => props.ctl,
  (ctl) => {
    if (ctl) last.value = { name: props.name, ctl, label: props.label }
  },
  { immediate: true },
)
const len = computed(() => catalog.params[last.value.name]?.length ?? 0)
</script>

<template>
  <Dialog
    :open="!!name && !!ctl"
    content-class="mx-auto max-w-[720px] p-6"
    @update:open="!$event && emit('close')"
  >
    <template #title>
      <div class="mb-1 flex items-baseline gap-3.5">
        <h2 class="text-[15px] font-bold tracking-[.18em] text-amber-bright">{{ last.label }}</h2>
        <span
          class="font-mono text-[11px] tracking-normal tabular-nums"
          :class="len > last.ctl?.maxLength * 0.9 ? 'text-amber-bright' : 'text-muted-foreground'"
          translate="no"
        >{{ len }}/{{ last.ctl?.maxLength }}</span>
      </div>
    </template>
    <Textarea
      v-model="catalog.params[last.name]"
      :rows="16"
      :maxlength="last.ctl?.maxLength"
      :spellcheck="last.ctl?.spellcheck ?? false"
      :aria-label="last.label"
      class="mt-4 max-h-[60vh] text-[13px]"
      translate="no"
    />

    <div class="mt-4 flex justify-end">
      <button
        type="button"
        class="obs-tr h-7 cursor-pointer rounded-sm border border-control px-3.5 font-sans text-[11.5px] font-bold tracking-[.08em] text-muted-foreground hover:border-amber hover:text-foreground active:scale-95"
        @click="emit('close')"
      >{{ t('panel.done') }}</button>
    </div>
  </Dialog>
</template>
