<script setup>
import { cn } from '@/lib/utils'
import { PhX } from '@phosphor-icons/vue'
import {
  DialogClose,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
  DialogDescription,
} from 'radix-vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  contentClass: { type: String, default: '' },
  maxWidth: { type: String, default: '960px' },
  closeLabel: { type: String, default: '' },
})
const emit = defineEmits(['update:open'])
</script>

<template>
  <DialogRoot :open="open" @update:open="emit('update:open', $event)">
    <slot name="trigger" />
    <DialogPortal>
      <!-- Radix Presence waits for closed-state keyframes before unmounting. -->
      <DialogOverlay class="fixed inset-0 z-50 bg-overlay/[0.82] data-[state=open]:animate-fade-in data-[state=closed]:animate-fade-out" />
      <DialogContent
        :style="{ maxWidth: props.maxWidth }"
        v-bind="$slots.description ? {} : { 'aria-describedby': undefined }"
        :class="cn('fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 data-[state=closed]:animate-fade-out')"
      >
        <!-- Keep zoom on a child so its transform cannot override the parent's centring translation. -->
        <div :class="cn('relative border border-hairline obs-elevated shadow-[0_32px_80px_-20px_hsl(var(--dome)/.95)] animate-zoom-in', contentClass)">
          <!-- Omit aria-describedby when there is no description slot, avoiding a dangling Radix ID. -->
          <DialogTitle v-if="$slots.title" as-child><slot name="title" /></DialogTitle>
          <DialogDescription v-if="$slots.description" as-child><slot name="description" /></DialogDescription>
          <slot />
          <DialogClose
            v-if="closeLabel"
            type="button"
            :title="closeLabel"
            :aria-label="closeLabel"
            class="obs-tr absolute end-3 top-3 flex h-11 w-11 items-center justify-center rounded-sm bg-[hsl(var(--edgeline))] text-foreground hover:shadow-[inset_0_0_0_999px_hsl(var(--foreground)/.12)] active:scale-95"
          ><PhX class="h-[18px] w-[18px]" aria-hidden="true" /></DialogClose>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
