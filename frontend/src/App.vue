<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { initStudio } from '@/stores/connection'
import { dismissNotice, runNoticeAction, toast } from '@/stores/notify'
import { PhX } from '@phosphor-icons/vue'

const { t } = useI18n()

onMounted(initStudio)
</script>

<template>
  <router-view />

  <!-- Keep announcements outside #app, which becomes inert while a modal is open. -->
  <Teleport to="body">
    <Transition name="toast">
      <div
        v-if="toast.notice"
        class="obs-panel fixed inset-x-0 top-7 z-[300] mx-auto flex w-fit max-w-[min(92vw,600px)] items-center gap-2 py-2 pl-4 font-mono text-[11px] tracking-[.12em] shadow-[0_4px_16px_hsl(var(--dome)/.5)]"
        :class="toast.sticky
          ? 'border border-destructive/70 pr-1.5 text-destructive'
          : ['border border-amber/50 text-amber-bright', toast.action ? 'pr-1.5' : 'pr-4']"
        :role="toast.sticky ? 'alert' : 'status'"
      >
        <span class="min-w-0">{{ toast.notice }}</span>
        <button
          v-if="toast.action"
          type="button"
          class="obs-tr h-7 shrink-0 cursor-pointer rounded-sm border border-amber/50 px-2.5 font-bold text-foreground hover:border-amber hover:bg-amber/10 active:scale-95"
          @click="runNoticeAction"
        >{{ toast.action.label }}</button>
        <button
          v-if="toast.sticky"
          type="button"
          class="obs-tr grid h-6 w-6 shrink-0 cursor-pointer place-items-center rounded-sm text-muted-foreground hover:bg-elevated hover:text-foreground active:scale-95"
          :aria-label="t('common.dismiss')"
          @click="dismissNotice"
        >
          <PhX class="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Centred with inset-x-0 + mx-auto rather than left-1/2, which would cap the width at half the viewport on phones. */
.toast-enter-active { transition: opacity .2s var(--ease-fluid), transform .2s var(--ease-fluid); }
.toast-leave-active { transition: opacity .16s ease-in, transform .16s ease-in; }
.toast-enter-from  { opacity: 0; transform: translateY(-8px); }
.toast-leave-to    { opacity: 0; transform: translateY(-4px); }
</style>
