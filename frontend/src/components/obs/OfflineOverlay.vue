<script setup>
/* The host must also make covered controls inert; the mask alone only blocks pointer access. */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { connection } from '@/stores/connection'

const { t } = useI18n()

const blocked = computed(() => !connection.comfyOnline)
// A live socket distinguishes engine downtime from a backend connection failure.
const engineDown = computed(() => connection.wsOnline && !connection.comfyOnline)

const now = ref(Date.now())
let clock = null
watch(
  blocked,
  (on) => {
    if (on) {
      now.value = Date.now()
      clock = setInterval(() => { now.value = Date.now() }, 1000)
    } else {
      clearInterval(clock)
      clock = null
    }
  },
  { immediate: true },
)
onUnmounted(() => clearInterval(clock))

const elapsed = computed(() => {
  const s = Math.max(0, Math.floor((now.value - (connection.offlineSince ?? now.value)) / 1000))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

const nextIn = computed(() =>
  connection.nextRetryAt ? Math.max(0, Math.ceil((connection.nextRetryAt - now.value) / 1000)) : null,
)

const meta = computed(() => {
  // No retry is scheduled before the first socket close or while only the engine is offline.
  if (engineDown.value || nextIn.value === null) return t('offline.metaWait', { elapsed: elapsed.value })
  return t('offline.metaRetry', { n: connection.reconnectAttempts, elapsed: elapsed.value, next: nextIn.value })
})
</script>

<template>
  <Transition name="offline">
    <div
      v-if="blocked"
      class="offline-mask absolute inset-0 z-[120] flex items-center justify-center bg-overlay/[.82]"
    >
      <div
        class="offline-card obs-elevated obs-corners mx-6 border border-hairline px-6 py-5 text-center shadow-[0_12px_40px_hsl(var(--dome)/.6)]"
      >
        <!-- Keep the changing countdown outside the alert to avoid repeating the status every second. -->
        <div role="alert">
          <p class="flex items-center justify-center gap-2 font-disp text-[12px] font-semibold tracking-[.28em] text-amber-bright">
            <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-destructive" aria-hidden="true" />
            {{ t(engineDown ? 'offline.title' : 'offline.reconnectTitle') }}
          </p>
          <p class="mt-2.5 font-sans text-[11.5px] leading-[1.8] tracking-[.04em] text-muted-foreground">
            {{ t(engineDown ? 'offline.desc' : 'offline.reconnectDesc') }}
          </p>
        </div>
        <p class="mt-3.5 border-t border-hairline pt-2.5 font-mono text-[11px] tabular-nums tracking-[.18em] text-ink-faint" translate="no" aria-hidden="true">
          {{ meta }}
        </p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.offline-enter-active { transition: opacity 160ms ease-out; }
.offline-leave-active { transition: opacity 130ms ease-out; }
.offline-enter-from,
.offline-leave-to { opacity: 0; }

.offline-enter-active .offline-card { transition: opacity 160ms var(--ease-fluid), transform 160ms var(--ease-fluid); }
.offline-leave-active .offline-card { transition: opacity 130ms ease-out, transform 130ms ease-out; }
.offline-enter-from .offline-card { opacity: 0; transform: translateY(4px); }
.offline-leave-to .offline-card { opacity: 0; transform: translateY(2px); }
</style>
