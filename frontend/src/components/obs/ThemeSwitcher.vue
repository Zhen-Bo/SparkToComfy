<script setup>
import { nextTick, ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { THEMES, setTheme, getTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { PhPalette, PhCheck } from '@phosphor-icons/vue'

const { t } = useI18n()

const open = ref(false)
const current = ref('amber')
const root = ref(null)
const triggerBtn = ref(null)
const itemRefs = ref([])
const menuStyle = ref({})

/** Position in viewport coordinates; the menu lives on body to escape panel overflow clipping. */
function place() {
  if (!root.value) return
  const r = root.value.getBoundingClientRect()
  menuStyle.value = { left: `${r.left}px`, top: `${r.bottom + 6}px` }
}
/** Menu semantics: opening moves focus to the current theme item; closing can return it to the trigger. */
async function toggle() {
  if (!open.value) place()
  open.value = !open.value
  if (open.value) {
    await nextTick()
    const i = THEMES.findIndex((t) => t.id === current.value)
    itemRefs.value[i >= 0 ? i : 0]?.focus()
  }
}
function closeMenu({ refocus = false } = {}) {
  if (!open.value) return
  open.value = false
  if (refocus) nextTick(() => triggerBtn.value?.focus())
}
/** Keys inside the menu: up/down move, Home/End jump, ESC closes and returns focus, Tab closes. */
function onMenuKeydown(e) {
  const items = itemRefs.value
  const at = items.indexOf(document.activeElement)
  if (e.key === 'Escape') {
    e.preventDefault()
    return closeMenu({ refocus: true })
  }
  if (e.key === 'Tab') return closeMenu()
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    const d = e.key === 'ArrowDown' ? 1 : -1
    items[(at + d + items.length) % items.length]?.focus()
  }
  if (e.key === 'Home') {
    e.preventDefault()
    items[0]?.focus()
  }
  if (e.key === 'End') {
    e.preventDefault()
    items[items.length - 1]?.focus()
  }
}
function onDocClick(e) {
  if (root.value && !root.value.contains(e.target) && !e.target.closest('[data-theme-menu]')) closeMenu()
}
function onWinResize() {
  if (open.value) place()
}
/* /playground is a long page, and the menu is fixed, so scrolling would detach it from the trigger.
   Tracking scroll in the capture phase also covers inner scroll containers. */
function onScroll() {
  if (open.value) place()
}
onMounted(() => {
  current.value = getTheme()
  document.addEventListener('click', onDocClick)
  window.addEventListener('resize', onWinResize)
  document.addEventListener('scroll', onScroll, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  window.removeEventListener('resize', onWinResize)
  document.removeEventListener('scroll', onScroll, true)
})

function pick(id) {
  setTheme(id)
  current.value = id
  closeMenu({ refocus: true })
}
</script>

<template>
  <div ref="root" class="relative">
    <button
      ref="triggerBtn"
      type="button"
      :title="t('theme.switch')"
      :aria-label="t('theme.switch')"
      aria-haspopup="menu"
      :aria-expanded="open"
      :class="cn(
        'obs-tr flex h-8 w-8 items-center justify-center rounded-sm border active:scale-95',
        open ? 'border-amber text-amber' : 'border-control text-muted-foreground hover:border-amber hover:text-foreground',
      )"
      @click.stop="toggle"
      @keydown.esc="closeMenu({ refocus: false })"
    >
      <PhPalette class="h-3.5 w-3.5" aria-hidden="true" />
    </button>

    <Teleport to="body">
      <Transition name="ts-menu">
        <div
          v-if="open"
          data-theme-menu
          role="menu"
          :aria-label="t('theme.menu')"
          class="obs-elevated fixed z-[130] w-[228px] overflow-hidden rounded-md border border-hairline shadow-[0_18px_44px_-14px_hsl(var(--dome)/.9)]"
          :style="menuStyle"
          @keydown="onMenuKeydown"
        >
        <button
          v-for="(theme, i) in THEMES"
          :key="theme.id"
          :ref="(el) => (itemRefs[i] = el)"
          type="button"
          role="menuitemradio"
          :aria-checked="theme.id === current"
          :class="cn(
            'obs-tr flex w-full items-center gap-3 border-b border-hairline/60 px-3 py-2.5 text-left last:border-b-0',
            theme.id === current ? 'bg-inset' : 'hover:bg-inset/60',
          )"
          @click.stop="pick(theme.id)"
        >
          <span class="flex gap-1" aria-hidden="true">
            <i v-for="(c, j) in theme.sw" :key="j" class="h-3 w-3 rounded-[3px] border border-foreground/20" :style="{ background: c }" />
          </span>
          <span class="min-w-0 flex-1 text-[12px] font-medium leading-tight">{{ t(theme.nameKey) }}</span>
          <PhCheck v-if="theme.id === current" class="h-3.5 w-3.5 shrink-0 text-amber" aria-hidden="true" />
        </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
/*
  The theme menu uses a transition, so rapid clicks redirect it instead of dropping frames.
  It scales out of the trigger: anchored to the trigger top-left corner, with transform-origin top left, starting at .97.
  Exit at 120ms is faster than the 150ms entry.
*/
.ts-menu-enter-active { transition: opacity 150ms var(--ease-fluid), transform 150ms var(--ease-fluid); transform-origin: top left; }
.ts-menu-leave-active { transition: opacity 120ms var(--ease-fluid), transform 120ms var(--ease-fluid); transform-origin: top left; }
.ts-menu-enter-from,
.ts-menu-leave-to { opacity: 0; transform: scale(.97); }
</style>
