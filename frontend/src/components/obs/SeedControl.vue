<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalog } from '@/stores/catalog'
import { cn } from '@/lib/utils'
import { PhDiceFive, PhLock, PhLockOpen } from '@phosphor-icons/vue'

const { t } = useI18n()

const seed = computed(() => catalog.params.seed ?? -1)

function onInput(e) {
  // Digits 0-9 only.
  // An empty field means -1 (random); only the dice button sets random.
  const digits = e.target.value.replace(/\D/g, '')
  e.target.value = digits
  catalog.params.seed = digits === '' ? -1 : parseInt(digits, 10)
}
// -1 is the readout for random.
// Focus selects it all so new input replaces it instead of merging with what is left behind, which would turn a typed 3 into 13.
function onFocus(e) {
  if (seed.value === -1) e.target.select()
}
// On blur with no new value, still random, restore the -1 readout.
function onBlur(e) {
  if (seed.value === -1) e.target.value = '-1'
}
function roll() {
  catalog.params.seed = -1 // -1 means random
}
</script>

<template>
  <div class="flex gap-[7px]">
    <div class="relative flex-1">
      <!-- Random shows the -1 readout plus the random badge.
           Focus selects it all so the next keystroke replaces it, see the script above. -->
      <input
        type="text"
        inputmode="numeric"
        name="seed"
        :aria-label="t('seed.fieldAria')"
        autocomplete="off"
        :value="seed"
        :disabled="catalog.seedLocked"
        @input="onInput"
        @focus="onFocus"
        @blur="onBlur"
        :class="cn(
          'h-9 w-full rounded-md border border-control obs-inset px-3 font-mono text-[13px] text-foreground obs-tr',
          'focus-visible:border-amber',
          'disabled:cursor-not-allowed disabled:opacity-50',
        )"
        spellcheck="false"
      />
      <span
        v-if="seed === -1"
        class="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded-sm border border-amber-dim px-1.5 py-px font-sans text-[11px] tracking-[.1em] text-amber"
      >{{ t('seed.random') }}</span>
    </div>
    <button
      type="button"
      :title="t('seed.resetRandom')"
      :aria-label="t('seed.resetRandom')"
      :disabled="catalog.seedLocked"
      class="obs-tr flex h-9 w-10 shrink-0 items-center justify-center rounded-md border border-control obs-inset text-muted-foreground hover:border-amber hover:text-amber active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-control disabled:hover:text-muted-foreground"
      @click="roll"
    >
      <PhDiceFive class="h-4 w-4" aria-hidden="true" />
    </button>
    <button
      type="button"
      :title="catalog.seedLocked ? t('seed.unlock') : t('seed.lock')"
      :aria-label="catalog.seedLocked ? t('seed.unlock') : t('seed.lock')"
      :aria-pressed="catalog.seedLocked"
      :class="cn(
        'obs-tr flex h-9 w-10 shrink-0 items-center justify-center rounded-md border active:scale-95',
        catalog.seedLocked
          ? 'border-amber bg-amber text-primary-foreground'
          : 'border-control obs-inset text-muted-foreground hover:border-amber hover:text-amber',
      )"
      @click="catalog.seedLocked = !catalog.seedLocked"
    >
      <PhLock v-if="catalog.seedLocked" class="h-4 w-4" aria-hidden="true" />
      <PhLockOpen v-else class="h-4 w-4" aria-hidden="true" />
    </button>
  </div>
</template>
