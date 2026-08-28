<script setup>
/**
 * Full-page confirmation (alertdialog) for clearing all history.
 * A mask plus a centred panel (obs-elevated with the obs-corners viewfinder brackets).
 * No timed steps: focus lands on the safe default, back; Tab cycles between the two buttons; ESC or a click on the mask goes back; only confirm clears.
 * Outer behaviour matches HistoryViewer: teleported to body, with #app inert while open.
*/
import { onMounted, onUnmounted, ref } from 'vue'
import { useModalLayer } from '@/lib/useModalLayer'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  /** How many images will be cleared; the readout inside the description. */
  count: { type: Number, required: true },
})
const emit = defineEmits(['confirm', 'cancel'])

const backBtn = ref(null)
const yesBtn = ref(null)

function onKeydown(e) {
  if (e.key === 'Escape') return emit('cancel')
  // Focus loop: two buttons cycling into each other, a second guard beside inert, the same as HistoryViewer.
  if (e.key === 'Tab') {
    e.preventDefault()
    ;(document.activeElement === backBtn.value ? yesBtn : backBtn).value?.focus()
  }
}

// The shared overlay layer handles the inert background and moves focus to the safe default, back.
useModalLayer(backBtn)
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[250]">
      <div class="chd-mask absolute inset-0 bg-overlay/[.82]" />
      <!-- Centring uses flex: the zoom keyframe animates transform and must not share an element with -translate centring, see the note in Dialog.vue -->
      <div class="absolute inset-0 flex items-center justify-center" @click.self="emit('cancel')">
        <div
          class="chd-panel obs-elevated obs-corners w-[340px] border border-hairline p-5 shadow-[0_12px_40px_hsl(var(--dome)/.6)]"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="chd-title"
          aria-describedby="chd-desc"
        >
          <div id="chd-title" class="font-sans text-[13.5px] font-bold tracking-[.06em] text-foreground">{{ t('history.clear.title') }}</div>
          <p id="chd-desc" class="mt-2 font-sans text-[12px] leading-[1.8] text-muted-foreground">
            <i18n-t scope="global" keypath="history.clear.desc">
              <template #count><span class="font-mono tabular-nums text-amber-bright" translate="no">{{ count }}</span></template>
            </i18n-t>
          </p>
          <div class="mt-[18px] flex justify-end gap-2">
            <button
              ref="backBtn"
              type="button"
              class="obs-tr h-7 cursor-pointer rounded-sm border border-control px-3.5 font-sans text-[11.5px] font-bold tracking-[.08em] text-muted-foreground hover:border-amber hover:text-foreground active:scale-95"
              @click="emit('cancel')"
            >{{ t('history.clear.back') }}</button>
            <button
              ref="yesBtn"
              type="button"
              class="obs-tr h-7 cursor-pointer rounded-sm border border-destructive/70 px-3.5 font-sans text-[11.5px] font-bold tracking-[.08em] text-destructive hover:border-destructive hover:bg-destructive/15 active:scale-95"
              @click="emit('confirm')"
            >{{ t('history.clear.confirm') }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/*
  Entry and exit use a Vue Transition, so an interruption redirects instead of replaying from zero.
  The mask animates opacity only; the panel animates opacity plus a slight scale.
  Exit at 130ms is faster than the 160ms entry, because leaving should be decisive.
*/
.chd-enter-active .chd-mask  { transition: opacity 160ms ease-out; }
.chd-leave-active .chd-mask  { transition: opacity 130ms ease-out; }
.chd-enter-from   .chd-mask,
.chd-leave-to     .chd-mask  { opacity: 0; }

.chd-enter-active .chd-panel { transition: opacity 160ms var(--ease-fluid), transform 160ms var(--ease-fluid); }
.chd-leave-active .chd-panel { transition: opacity 130ms ease-out, transform 130ms ease-out; }
.chd-enter-from   .chd-panel { opacity: 0; transform: translateY(4px) scale(.98); }
.chd-leave-to     .chd-panel { opacity: 0; transform: translateY(2px) scale(.98); }
</style>
