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
      <!-- radix-vue Presence waits for the animation before unmounting, so a keyframe on the closed state gives the fade-out.
           The exit touches opacity only: a transform would break the -translate-x/y-1/2 centering on DialogContent, see below. -->
      <DialogOverlay class="fixed inset-0 z-50 bg-overlay/[0.82] data-[state=open]:animate-fade-in data-[state=closed]:animate-fade-out" />
      <DialogContent
        :style="{ maxWidth: props.maxWidth }"
        v-bind="$slots.description ? {} : { 'aria-describedby': undefined }"
        :class="cn('fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 data-[state=closed]:animate-fade-out')"
      >
        <!--
          The visual box is nested and carries the entry animation.
          A transform in the keyframes overrides the translate utility on the same element for the length of the animation, so a zoom must never share an element with -translate-x/y-1/2 centering: the dialog would start down and to the right and snap to the centre.
          Separating them structurally is what makes it safe.
          -->
        <div :class="cn('relative border border-hairline obs-elevated shadow-[0_32px_80px_-20px_hsl(var(--dome)/.95)] animate-zoom-in', contentClass)">
          <!-- radix requires a DialogTitle; the description goes through DialogDescription and aria-describedby is wired automatically.
               With no description, binding aria-describedby to undefined makes Vue drop the attribute entirely, and the radix check stops warning once it is absent.
               The string "undefined" would not work, because it tests presence, not value. -->
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
