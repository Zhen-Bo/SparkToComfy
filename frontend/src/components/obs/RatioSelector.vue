<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalog, controls } from '@/stores/catalog'
import { locked, run } from '@/stores/run'
import { cn } from '@/lib/utils'
import { PhArrowsLeftRight } from '@phosphor-icons/vue'

const { t } = useI18n()
// Labels for the two resolution tiers.
// The locale never changes at runtime, so reading them during setup is enough.
const tiers = [t('ratio.standard'), t('ratio.highres')]

// The submitted value has exactly three keys: preset, highres, landscape.
// The backend looks the dimensions up; the frontend never sends them.
const presets = computed(() => controls.value.size?.presets ?? {})
const keys = computed(() => Object.keys(presets.value))
const size = computed(() => catalog.params.size ?? { preset: null, highres: false, landscape: false })

/* Locked while generating.
   inert plus pointer-events-none stops a real mouse and keyboard but not a programmatic click.
   The contract in this project is that whatever is declared unavailable must really be a no-op (see the aria-disabled note in GenerateButton), so every entry that writes the store guards itself.
   The flag itself is the shared locked from run.js. */
const setPreset = (k) => { if (!locked.value) catalog.params.size.preset = k }
const setTier = (hi) => { if (!locked.value) catalog.params.size.highres = hi }
const toggleLandscape = () => { if (!locked.value) catalog.params.size.landscape = !catalog.params.size.landscape }

/** Outline size of each ratio glyph inside the 30x28 viewBox.
 * The base is always square or portrait; landscape comes from swapping width and height. */
const GLYPHS = { square: [20, 20], poster: [15, 24], photo: [18, 24], wallpaper: [14, 25] }

function glyphBox(p) {
  const a = p.standard.width / p.standard.height
  let [w, h] = GLYPHS[p.icon] ?? (a >= 1 ? [24, 24 / a] : [24 * a, 24])
  if (size.value.landscape) [w, h] = [h, w]
  return { x: (30 - w) / 2, y: (28 - h) / 2, w, h }
}

/** The ratio text turns with the swap: 2:3 becomes 3:2. */
function shownRatio(label) {
  if (!size.value.landscape) return label
  const [a, b] = String(label).split(':')
  return b ? `${b}:${a}` : label
}

/** The corner marks are four fixed-shape paths, each a 3px stroke drawn from the origin and placed with a CSS transform.
    A transform can be transitioned, so switching ratio or orientation slides them to the new position instead of jumping. */
function glyphCorners(p) {
  const { x, y, w, h } = glyphBox(p)
  return [
    { tx: x, ty: y, d: 'M0 0 l-3 -3' },
    { tx: x + w, ty: y, d: 'M0 0 l3 -3' },
    { tx: x, ty: y + h, d: 'M0 0 l-3 3' },
    { tx: x + w, ty: y + h, d: 'M0 0 l3 3' },
  ]
}

/* The APG radiogroup keyboard contract: a roving tabindex, so the group takes a single Tab stop, and arrow keys that move and select at once. */
const ratioRefs = ref([])
const tierRefs = ref([])
const ARROW_D = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

function onRatioKey(e, i) {
  if (locked.value) return
  const d = ARROW_D[e.key]
  if (!d) return
  e.preventDefault()
  const next = (i + d + keys.value.length) % keys.value.length
  catalog.params.size.preset = keys.value[next]
  ratioRefs.value[next]?.focus()
}
function onTierKey(e, i) {
  if (locked.value) return
  const d = ARROW_D[e.key]
  if (!d) return
  e.preventDefault()
  const next = (i + d + 2) % 2
  catalog.params.size.highres = next === 1
  tierRefs.value[next]?.focus()
}
</script>

<template>
  <!-- The whole size area is locked while generating.
       The viewfinder aspect ratio follows currentDims, so changing the size mid-run would force preview frames still arriving at the old ratio into the new frame and put black bars down the sides: the screen would be lying.
       A change also cannot affect a job already submitted; it would only make the output-size readout disagree with the work in flight. inert rather than disabled, so focus does not evaporate onto body, the same as the offline overlay. -->
  <div :inert="run.busy || null" :class="run.busy && 'pointer-events-none opacity-50'">
    <div class="grid grid-cols-4 gap-[7px]" role="radiogroup" :aria-label="t('ratio.groupAria')">
      <button
        v-for="(k, i) in keys"
        :key="k"
        :ref="(el) => (ratioRefs[i] = el)"
        type="button"
        role="radio"
        :aria-checked="size.preset === k"
        :aria-label="shownRatio(presets[k].label)"
        :tabindex="size.preset === k ? 0 : -1"
        :class="cn(
          'obs-tr flex flex-col items-center gap-1.5 rounded-md border obs-inset px-1 pb-1.5 pt-2 active:scale-95',
          size.preset === k ? 'border-amber' : 'border-control hover:border-amber',
        )"
        @click="setPreset(k)"
        @keydown="onRatioKey($event, i)"
      >
        <svg width="30" height="28" viewBox="0 0 30 28" aria-hidden="true">
          <!-- The rect geometry is written as both attributes and style: a browser that supports CSS geometry properties gets the .glyph-anim transition, while an older one falls back to the attributes and updates instantly, with no animation but nothing broken. -->
          <rect
            class="glyph-anim"
            :x="glyphBox(presets[k]).x" :y="glyphBox(presets[k]).y" :width="glyphBox(presets[k]).w" :height="glyphBox(presets[k]).h"
            :style="{ x: `${glyphBox(presets[k]).x}px`, y: `${glyphBox(presets[k]).y}px`, width: `${glyphBox(presets[k]).w}px`, height: `${glyphBox(presets[k]).h}px` }"
            fill="none" :stroke="size.preset === k ? 'hsl(var(--amber-bright))' : 'hsl(var(--ink-faint))'" stroke-width="1.4"
          />
          <path
            v-for="(c, ci) in glyphCorners(presets[k])"
            :key="ci"
            class="glyph-anim"
            :d="c.d" :style="{ transform: `translate(${c.tx}px, ${c.ty}px)` }"
            fill="none" :stroke="size.preset === k ? 'hsl(var(--amber-bright))' : 'hsl(var(--ink-faint))'" stroke-width="1"
          />
        </svg>
        <span
          class="font-mono text-[11px]"
          :class="size.preset === k ? 'text-amber-bright' : 'text-muted-foreground'"
        >{{ shownRatio(presets[k].label) }}</span>
      </button>
    </div>

    <div class="mt-2 flex gap-[7px]">
      <div class="flex flex-1 rounded-md border border-control obs-inset p-[3px]" role="radiogroup" :aria-label="t('ratio.tierAria')">
        <button
          v-for="(label, tier) in tiers"
          :key="tier"
          :ref="(el) => (tierRefs[tier] = el)"
          type="button"
          role="radio"
          :aria-checked="size.highres === (tier === 1)"
          :tabindex="size.highres === (tier === 1) ? 0 : -1"
          :class="cn(
            'obs-tr flex-1 rounded-[4px] py-2 font-sans text-[12.5px] font-semibold tracking-[.08em] active:scale-95',
            size.highres === (tier === 1)
              ? 'text-amber-bright shadow-[inset_0_0_0_1px_hsl(var(--amber)/.55)] bg-amber/10'
              : 'text-muted-foreground hover:text-foreground',
          )"
          @click="setTier(tier === 1)"
          @keydown="onTierKey($event, tier)"
        >{{ label }}</button>
      </div>
      <button
        type="button"
        :title="t('ratio.swap')"
        :aria-label="t('ratio.swap')"
        :aria-pressed="size.landscape"
        :class="cn(
          'obs-tr flex w-[42px] items-center justify-center rounded-md border active:scale-95',
          size.landscape ? 'border-amber text-amber obs-inset' : 'border-control obs-inset text-muted-foreground hover:border-amber hover:text-foreground',
        )"
        @click="toggleLandscape()"
      >
        <PhArrowsLeftRight class="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<style scoped>
/* Turning the ratio box: the box geometry, through CSS geometry properties, and the corner offsets both use a 220ms fluid ease.
   What changes is the state itself, one box deforming, not a decorative entry. obs-tr does not cover SVG geometry properties, so this uses a local class.
   Reduced motion is handled by the global !important rule in style.css, which collapses it to nearly instant. */
.glyph-anim {
  transition:
    x 0.22s var(--ease-fluid),
    y 0.22s var(--ease-fluid),
    width 0.22s var(--ease-fluid),
    height 0.22s var(--ease-fluid),
    transform 0.22s var(--ease-fluid),
    stroke 0.2s var(--ease-fluid);
}
</style>
