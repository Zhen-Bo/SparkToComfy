<script setup>
/**
 * The offline overlay covers the whole panel area below the header when ComfyUI or the backend goes offline.
 * The mask absorbs pointer events.
 * It darkens without blurring (bg-overlay/[.82], the same density as the Dialog mask), so the panel hairlines and control outlines stay sharp and frozen and the sense of structure survives.
 * The header, connection badge included, stays reachable outside the overlay scope.
 * The positioning anchor is the relative parent, ParameterPanel.
 * The bottom row of the card is the reconnect readout, ticking every second: a waiting timer when the engine is down, and retry count plus timer plus the next backoff countdown when the backend is down.
 * The numbers come from offlineSince, reconnectAttempts and nextRetryAt in the store; api/comfy.js decides the backoff.
 * The single trigger is connection.comfyOnline being false, which covers both ways down: the socket is up but ComfyUI is offline (reported by the system event), and the socket itself dropped (onClose clears comfyOnline too).
 * Recovery is automatic: the socket reconnects, the next system arrives and the overlay disappears with no user action.
 * Layers: z-[120] sits over the dropdowns inside the panel at z-50, while the theme menu at z-[130] deliberately sits over this one, because its trigger in the header must stay reachable (see ThemeSwitcher).
 * Blocking is two gates: this layer absorbs the pointer, and ParameterPanel sets :inert on the sibling layer to lock Tab and screen readers out of everything below the header.
*/
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { connection } from '@/stores/connection'

const { t } = useI18n()

const blocked = computed(() => !connection.comfyOnline)
/** Socket still up means the ComfyUI engine itself is offline; socket down means the backend is unreachable and api/comfy.js is reconnecting. */
const engineDown = computed(() => connection.wsOnline && !connection.comfyOnline)

/* The reconnect readout counts mm:ss from going offline, ticking every second: pure waiting when the engine died, retry counts when the backend dropped.
   The moving numbers are a measure for the eye and stay out of the announcement.
   The progress row is aria-hidden and screen readers get the stable description instead, said once through role=alert. */
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

/** Seconds until the next reconnect.
 * It exists only while the backend is down and the socket is backing off; when only the engine is offline the socket is still up and there is no retry loop. */
const nextIn = computed(() =>
  connection.nextRetryAt ? Math.max(0, Math.ceil((connection.nextRetryAt - now.value) / 1000)) : null,
)

const meta = computed(() => {
  // Before the first onClose, a few hundred milliseconds in, no schedule exists yet, so show the elapsed timer only rather than a fake RETRY #0 or NEXT 0s.
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
        <!-- role=alert wraps the status only.
             The readout changes every second, and inside the alert that would re-announce the whole aria-atomic block each time, the same problem already fixed in QueueSlots. aria-hidden is not a reliable guard because screen readers disagree about it, so the readout lives outside. -->
        <div role="alert">
          <p class="flex items-center justify-center gap-2 font-disp text-[12px] font-semibold tracking-[.28em] text-amber-bright">
            <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-destructive" aria-hidden="true" />
            {{ t(engineDown ? 'offline.title' : 'offline.reconnectTitle') }}
          </p>
          <p class="mt-2.5 font-sans text-[11.5px] leading-[1.8] tracking-[.04em] text-muted-foreground">
            {{ t(engineDown ? 'offline.desc' : 'offline.reconnectDesc') }}
          </p>
        </div>
        <!-- Reconnect readout, ticking every second: for the eye, not for announcement -->
        <p class="mt-3.5 border-t border-hairline pt-2.5 font-mono text-[11px] tabular-nums tracking-[.18em] text-ink-faint" translate="no" aria-hidden="true">
          {{ meta }}
        </p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Same as ClearHistoryDialog: the mask animates opacity only, the card fades in from 4px below, and the 130ms exit is faster than the entry. */
.offline-enter-active { transition: opacity 160ms ease-out; }
.offline-leave-active { transition: opacity 130ms ease-out; }
.offline-enter-from,
.offline-leave-to { opacity: 0; }

.offline-enter-active .offline-card { transition: opacity 160ms var(--ease-fluid), transform 160ms var(--ease-fluid); }
.offline-leave-active .offline-card { transition: opacity 130ms ease-out, transform 130ms ease-out; }
.offline-enter-from .offline-card { opacity: 0; transform: translateY(4px); }
.offline-leave-to .offline-card { opacity: 0; transform: translateY(2px); }
</style>
