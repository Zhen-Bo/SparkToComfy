/* Hover-revealed controls stay visible on touch-capable hybrids even when their mouse supports hover. */
export const hoverCapable = typeof matchMedia !== 'undefined'
  && matchMedia('(hover: hover)').matches
  && !matchMedia('(any-pointer: coarse)').matches
