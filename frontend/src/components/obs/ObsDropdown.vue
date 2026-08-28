<script setup>
import { nextTick, ref, useId, onMounted, onBeforeUnmount } from 'vue'
import { cn } from '@/lib/utils'
import { PhCaretDown, PhCheck } from '@phosphor-icons/vue'

/**
 * Observatory-style dropdown.
 * items: [{ value, label, desc? }]
 * Accessibility follows the APG select-only combobox: the trigger is role="combobox" with aria-controls pointing at the listbox, focus stays on the trigger, arrow keys move the selection through aria-activedescendant, Enter and Space select, and ESC closes and returns focus to the trigger.
 * The role and aria-controls are not optional: aria-activedescendant only works on roles such as combobox, listbox and textbox, and on a plain button assistive technology ignores it, so the visual highlight moves while the screen reader stays silent.
*/
const props = defineProps({
  items: { type: Array, required: true },
  modelValue: { type: [String, Number], default: null },
  placeholder: { type: String, default: '—' },
  label: { type: String, default: null }, // accessible name, the section label
})
const emit = defineEmits(['update:modelValue', 'change'])

const open = ref(false)
const root = ref(null)
const menuEl = ref(null)
const activeIdx = ref(-1)

/* The menu is teleported to body and positioned fixed.
   As an absolute child of the scroll box, a picker near the bottom of the panel had its menu clipped by overflow-y-auto: at 1280x720 the sampler lost 2 of 5 options and the scheduler 2 of 3, unreachable by mouse, though the keyboard was fine because of scrollIntoView.
   It follows ThemeSwitcher: position on open, and recompute on resize and on scroll in the capture phase. */
const GAP = 4
const EDGE = 8
const menuStyle = ref({})
function place() {
  const r = root.value?.getBoundingClientRect()
  if (!r) return
  menuStyle.value = { left: `${r.left}px`, top: `${r.bottom + GAP}px`, width: `${r.width}px` }
  // Flip above the trigger when there is no room below.
  // The real height is only known after mount, so this runs then.
  nextTick(() => {
    const m = menuEl.value?.getBoundingClientRect()
    if (!m) return
    if (m.bottom > window.innerHeight - EDGE && r.top - m.height - GAP > EDGE)
      menuStyle.value = { ...menuStyle.value, top: `${r.top - m.height - GAP}px` }
  })
}

const uid = useId()
const optionId = (i) => `${uid}-opt-${i}`
const listboxId = `${uid}-listbox`

function openMenu() {
  place()
  open.value = true
  activeIdx.value = Math.max(0, props.items.findIndex((i) => i.value === props.modelValue))
}
function closeMenu({ refocus = false } = {}) {
  open.value = false
  activeIdx.value = -1
  if (refocus) nextTick(() => root.value?.querySelector('button')?.focus())
}

function pick(item) {
  if (item.disabled) return // an option the declaration marks disabled is blocked here, for both click and Enter
  emit('update:modelValue', item.value)
  emit('change', item.value)
  closeMenu({ refocus: true })
}

function onTriggerClick() {
  open.value ? closeMenu() : openMenu()
}

/** Move activedescendant and keep the new option in view. */
function moveActive(to) {
  activeIdx.value = to
  nextTick(() => document.getElementById(optionId(activeIdx.value))?.scrollIntoView({ block: 'nearest' }))
}
const stepActive = (d) => moveActive((activeIdx.value + d + props.items.length) % props.items.length)
function pickActive() {
  const item = props.items[activeIdx.value]
  if (item) pick(item)
}

/* Keys that act only while the menu is open.
   ESC keeps stopPropagation without preventDefault: it must not reach an overlay behind the menu, but the browser default is harmless. */
const OPEN_KEYS = {
  Escape: (e) => { e.stopPropagation(); closeMenu({ refocus: true }) },
  ArrowDown: (e) => { e.preventDefault(); stepActive(1) },
  ArrowUp: (e) => { e.preventDefault(); stepActive(-1) },
  Home: (e) => { e.preventDefault(); moveActive(0) },
  End: (e) => { e.preventDefault(); moveActive(props.items.length - 1) },
  Enter: (e) => { e.preventDefault(); pickActive() },
  ' ': (e) => { e.preventDefault(); pickActive() },
}

/** Keyboard: up and down open the menu and move activedescendant, Enter and Space select, ESC closes. */
function onTriggerKeydown(e) {
  // While closed only the arrows act. Every other key is left to the button, so Enter and Space still click it open.
  if (!open.value) {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    e.preventDefault()
    return openMenu()
  }
  OPEN_KEYS[e.key]?.(e)
}

/* Closing on focus loss listens to pointerdown in the capture phase, because a click can be stopped elsewhere, for instance by @click.stop on another dropdown trigger, leaving focus moved but this menu still open.
   Capturing focusin covers leaving by Tab.
   A target outside root counts as focus loss. */
function onDocFocusOut(e) {
  if (!open.value) return
  // The teleported menu is no longer under root.
  // Checking root alone would close the menu during pointerdown, and the click would never land on an option.
  const inside = root.value?.contains(e.target) || menuEl.value?.contains(e.target)
  if (!inside) closeMenu()
}
function reposition() {
  if (open.value) place()
}
onMounted(() => {
  document.addEventListener('pointerdown', onDocFocusOut, true)
  document.addEventListener('focusin', onDocFocusOut, true)
  window.addEventListener('resize', reposition)
  document.addEventListener('scroll', reposition, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocFocusOut, true)
  document.removeEventListener('focusin', onDocFocusOut, true)
  window.removeEventListener('resize', reposition)
  document.removeEventListener('scroll', reposition, true)
})

function labelOf(v) {
  return props.items.find((i) => i.value === v)?.label ?? props.placeholder
}
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      role="combobox"
      :aria-label="label ?? undefined"
      aria-haspopup="listbox"
      :aria-controls="listboxId"
      :aria-expanded="open"
      :aria-activedescendant="open && activeIdx >= 0 ? optionId(activeIdx) : undefined"
      :class="cn(
        'obs-tr flex w-full items-center justify-between gap-2.5 rounded-md border obs-inset px-3 py-2.5 text-left font-mono text-[13px]',
        open ? 'border-amber' : 'border-control hover:border-amber',
      )"
      @click.stop="onTriggerClick"
      @keydown="onTriggerKeydown"
    >
      <span class="truncate" translate="no">{{ labelOf(modelValue) }}</span>
      <PhCaretDown class="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200 ease-[var(--ease-fluid)]" :class="open && 'rotate-180'" aria-hidden="true" />
    </button>

    <Teleport to="body">
      <Transition name="odd-menu">
        <div
          v-if="open"
          :id="listboxId"
          ref="menuEl"
          role="listbox"
          :aria-label="label ?? undefined"
          :style="menuStyle"
          class="obs-elevated fixed z-[110] max-h-[280px] overflow-y-auto overscroll-contain rounded-md border border-edgeline shadow-[0_18px_44px_-14px_hsl(var(--dome)/.95),0_3px_10px_hsl(var(--dome)/.5)]"
        >
          <div
            v-for="(item, i) in items"
            :id="optionId(i)"
            :key="item.value"
            role="option"
            :aria-selected="item.value === modelValue"
            :aria-disabled="item.disabled || undefined"
            :class="cn(
              'obs-tr flex items-center justify-between gap-2 border-b border-hairline/60 px-3 py-2.5 last:border-b-0',
              item.disabled
                ? 'cursor-not-allowed opacity-40'
                : 'cursor-pointer hover:bg-inset/70',
              item.value === modelValue && 'bg-inset shadow-[inset_2px_0_0_hsl(var(--amber))]',
              i === activeIdx && !item.disabled && 'bg-inset/70',
            )"
            @click.stop="pick(item)"
            @mouseenter="activeIdx = i"
          >
            <div class="min-w-0">
              <div class="truncate font-mono text-[12.5px]" translate="no">{{ item.label }}</div>
              <div v-if="item.desc" class="mt-0.5 font-mono text-[11px] text-ink-faint" translate="no">{{ item.desc }}</div>
            </div>
            <PhCheck v-if="item.value === modelValue" class="h-3.5 w-3.5 shrink-0 text-amber" aria-hidden="true" />
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
/*
  A transition rather than keyframes, so toggling quickly redirects from wherever it is instead of replaying from zero.
  The popover scales out of the trigger: origin at top centre, opening downward at the trigger width, starting at .97 and never at scale(0).
  Exit at 120ms is faster than the 150ms entry.
*/
.odd-menu-enter-active { transition: opacity 150ms var(--ease-fluid), transform 150ms var(--ease-fluid); transform-origin: top center; }
.odd-menu-leave-active { transition: opacity 120ms var(--ease-fluid), transform 120ms var(--ease-fluid); transform-origin: top center; }
.odd-menu-enter-from,
.odd-menu-leave-to { opacity: 0; transform: scale(.97); }
</style>
