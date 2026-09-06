<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useModalLayer } from '@/lib/useModalLayer'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  count: { type: Number, required: true },
})
const emit = defineEmits(['confirm', 'cancel'])

const backBtn = ref(null)
const yesBtn = ref(null)

function onKeydown(e) {
  if (e.key === 'Escape') return emit('cancel')
  if (e.key === 'Tab') {
    e.preventDefault()
    ;(document.activeElement === backBtn.value ? yesBtn : backBtn).value?.focus()
  }
}

// Start on the non-destructive action.
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
.chd-enter-active .chd-mask  { transition: opacity 160ms ease-out; }
.chd-leave-active .chd-mask  { transition: opacity 130ms ease-out; }
.chd-enter-from   .chd-mask,
.chd-leave-to     .chd-mask  { opacity: 0; }

.chd-enter-active .chd-panel { transition: opacity 160ms var(--ease-fluid), transform 160ms var(--ease-fluid); }
.chd-leave-active .chd-panel { transition: opacity 130ms ease-out, transform 130ms ease-out; }
.chd-enter-from   .chd-panel { opacity: 0; transform: translateY(4px) scale(.98); }
.chd-leave-to     .chd-panel { opacity: 0; transform: translateY(2px) scale(.98); }
</style>
