<script setup>
/**
 * The queue slots, a vocabulary used only while waiting in line: five fixed slots, with the overflow counted as +N text on the right.
 * solid amber = a job ahead, blinking = your position, ready = the first slot stays lit with a sweep band and the preparing message.
 * +N counts the people who do not fit, you included.
 * The readout is always the real number, and the slots stay centred whether or not +N shows.
 * The generating and upscaling phases do not share this vocabulary.
*/
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  ahead: { type: Number, default: 0 }, // jobs ahead, the real count
  eta: { type: String, default: '00:00' }, // estimated wait, mm:ss
  ready: { type: Boolean, default: false }, // your turn: preparing to generate
})
const TOTAL = 5

function slotCls(i) {
  if (props.ready) return { on: i === 1 }
  const n = Math.min(props.ahead, TOTAL)
  return { hd: i <= n, you: props.ahead < TOTAL && i === props.ahead + 1 }
}
const aheadLabel = computed(() => String(props.ahead).padStart(2, '0'))
const overflow = computed(() => (props.ahead >= TOTAL ? `+${props.ahead - TOTAL + 1}` : ''))
/* The live region announces phase changes only.
   An aria-label that follows the countdown would change every 650ms and a screen reader would fire seven times in a row.
   The per-second position belongs to the visual countdown; the reader only needs the phase. */
const announce = computed(() =>
  props.ready ? t('queue.announceReady') : t('queue.announceQueued'),
)
</script>

<template>
  <div class="qs">
    <span class="sr-only" role="status">{{ announce }}</span>
    <div class="qs-slots" :class="{ rdy: ready }" aria-hidden="true">
      <i v-for="i in TOTAL" :key="i" :class="slotCls(i)" />
      <span class="qs-more" :class="{ on: Boolean(overflow) }" translate="no">{{ overflow }}</span>
    </div>
    <div class="qs-copy" aria-hidden="true">
      <i18n-t scope="global" v-if="!ready" keypath="queue.ahead" tag="span" class="cline">
        <template #n><b class="qn" translate="no">{{ aheadLabel }}</b></template>
      </i18n-t>
      <span v-else class="cline rdy">{{ t('queue.preparing') }}</span>
      <span class="csub">
        <i18n-t scope="global" v-if="!ready" keypath="queue.eta">
          <template #eta><b class="qt" translate="no">{{ eta }}</b></template>
        </i18n-t>
        <template v-else>{{ t('queue.allocating') }}</template>
      </span>
    </div>
  </div>
</template>

<style scoped>
/* A slot is a place in line: solid amber is a job ahead, blinking is your position, and a steady first slot means ready.
   Five fixed slots, with the overflow counted as +N text on the right, absolutely positioned and animating opacity only. */
.qs { display: flex; flex-direction: column; align-items: center; gap: 15px; }
.qs-slots { position: relative; display: flex; align-items: center; gap: 6px; }
.qs-slots i { width: 14px; height: 14px; border: 1px solid hsl(var(--hairline)); background: transparent;
  transition: background-color .25s var(--ease-fluid), border-color .25s var(--ease-fluid), box-shadow .25s var(--ease-fluid), transform .25s var(--ease-fluid); }
.qs-slots i.hd { border-color: hsl(var(--amber-dim)); background: hsl(var(--amber) / .26); }
.qs-slots i.you { border-color: hsl(var(--amber-bright)); background: hsl(var(--amber)); box-shadow: 0 0 10px hsl(var(--amber) / .7); animation: qsBlink .9s ease-in-out infinite; }
.qs-slots i.on { border-color: hsl(var(--amber)); background: hsl(var(--amber)); transform: scale(1.2); animation: qsReady 1.6s ease-in-out infinite; }
@keyframes qsBlink { 0%, 100% { opacity: .45; transform: scale(1); } 50% { opacity: 1; transform: scale(1.18); } }
@keyframes qsReady { 0%, 100% { box-shadow: 0 0 10px hsl(var(--amber) / .6); } 50% { box-shadow: 0 0 20px hsl(var(--amber) / .95); } }

/* The ready sweep band: a 2s pass that fades in and out at each end.
   It animates background-position on purpose.
   That is paint-only over roughly 120x24px with no layout cost, while a transform would need an extra overflow clip box that would cut off the slot glow and the +N readout beside it. */
.qs-slots.rdy::after { content: ''; position: absolute; top: -5px; bottom: -5px; left: 0; right: 0; pointer-events: none;
  background: linear-gradient(90deg, transparent, hsl(var(--amber-bright) / .1) 50%, transparent); background-size: 60% 100%; background-repeat: no-repeat;
  animation: qsSweep 2s var(--ease-fluid) infinite; }
@keyframes qsSweep { 0% { background-position: -60% 0; opacity: 0; } 18% { opacity: 1; } 82% { opacity: 1; } 100% { background-position: 160% 0; opacity: 0; } }

/* The overflow readout: the five slots centre themselves and +N hangs outside the row on the right, so it never shifts that centring when it appears or disappears. */
.qs-more { position: absolute; left: calc(100% + 7px); top: 50%; transform: translateY(-50%); white-space: nowrap;
  font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 10px; font-weight: 700; letter-spacing: .04em;
  color: hsl(var(--amber-bright)); opacity: 0; transition: opacity .3s var(--ease-fluid); }
.qs-more.on { opacity: 1; }

.qs-copy { display: flex; flex-direction: column; align-items: center; gap: 5px; min-height: 40px; }
.cline { font-size: 13px; font-weight: 700; letter-spacing: .08em; color: hsl(var(--foreground)); }
.cline.rdy { color: hsl(var(--amber-bright)); animation: qsRdyTxt 1.6s ease-in-out infinite; }
.qn { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 14px; color: hsl(var(--amber-bright)); padding: 0 1px; }
.csub { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 10px; letter-spacing: .1em; color: hsl(var(--ink-faint)); }
.qt { color: hsl(var(--amber-bright)); font-variant-numeric: tabular-nums; }
@keyframes qsRdyTxt { 0%, 100% { opacity: .72; } 50% { opacity: 1; } }
</style>
