/**
 * Zoom and pan for the image viewer: wheel, drag, two-finger pinch, and a floor that is recomputed after a window resize.
 * All the geometry lives here; the caller only draws and routes the keyboard.
 *
 * Opening or switching images fits the image (scale = minScale), the ceiling is 400% and the zoom factor is never displayed.
 * Zoom steps geometrically, x1.12 and /1.12, and the wheel anchors on the cursor, the way browsers and Figma do it.
 * The viewing margin is 16px on all four sides, because the dock floats and takes no layout space.
 * Below 960px the side margins tighten to 8px and the stage reserves the top chrome and the bottom thumbnail panel.
 * Panning stops where the image edge meets the stage edge, so the image is always on screen and can never be lost.
*/

import { computed, onMounted, onUnmounted, ref } from 'vue'

export const MAX_SCALE = 4
export const ZOOM_FACTOR = 1.12 // geometric steps, so every notch feels the same, the standard for image viewers
export const PAN_STEP = 40 // pan step in px for Shift plus an arrow key
const EDGE = 16 // minimum distance between the image frame and each window edge
const NARROW = 960 // below this the layout is the phone one (MobileStudioView takes over at the same line)
const NARROW_TOP = 68 // the 44px top buttons plus their gap to the image
const NARROW_BOTTOM = 145 // the phone bottom panel: 128px thumbnail strip + 16px padding + 1px border (see HistoryViewer.vue)

export function useZoomPan(dims) {
  const scale = ref(1)
  const ox = ref(0)
  const oy = ref(0)
  const dragging = ref(false)
  const pinching = ref(false) // a two-finger pinch is in progress: no transform transition, grabbing cursor
  const winW = ref(window.innerWidth)
  const winH = ref(window.innerHeight)
  let dragFrom = null
  const pointers = new Map() // active pointers, pointerId to coordinates, used by the pinch gesture
  let pinchFrom = null

  const isLandscape = computed(() => dims.value.width > dims.value.height)

  const narrow = computed(() => winW.value < NARROW)
  const insets = computed(() => narrow.value ? { top: NARROW_TOP, bottom: NARROW_BOTTOM } : { top: EDGE, bottom: EDGE })

  const stageW = computed(() => winW.value - (narrow.value ? 8 : EDGE) * 2)
  const stageH = computed(() => winH.value - insets.value.top - insets.value.bottom)
  const centerY = computed(() => (winH.value + insets.value.top - insets.value.bottom) / 2)

  /** The long side wins: landscape images lock width, portrait and square lock height. */
  const frame = computed(() => {
    const a = dims.value.width / dims.value.height
    return isLandscape.value ? { w: stageW.value, h: stageW.value / a } : { w: stageH.value * a, h: stageH.value }
  })
  const frameStyle = computed(() => ({ width: `${frame.value.w}px`, height: `${frame.value.h}px` }))

  /** The zoom floor is whatever fits the stage; it drops below 1 for a landscape image that would bleed at 100%.
   * Two decimals keep the readout steady, and the rounding goes down: rounding to nearest can land above the true fit and push the image past the margin. */
  const minScale = computed(() => Math.min(1, Math.floor(Math.min(stageW.value / frame.value.w, stageH.value / frame.value.h) * 100) / 100))

  const transform = computed(() => `translate(${ox.value}px, ${oy.value}px) scale(${scale.value})`)

  /* While a gesture runs, dragging or pinching, the image transforms every frame and a full-screen backdrop-filter would resample and reblur on each one.
     The backdrop blur on the mask and the chrome is therefore disabled for the gesture, see .bd-off in style.css. */
  const gesturing = computed(() => dragging.value || pinching.value)

  function fitToStage() {
    scale.value = minScale.value
    ox.value = 0
    oy.value = 0
  }

  /** The offset ceiling is whatever the scaled image hides outside the stage.
   * Once an edge reaches the stage edge there is nothing further to reveal, so the pan stops; an image smaller than the stage has a ceiling of zero and stays centred. */
  function clampOffset() {
    const maxX = Math.max(0, (frame.value.w * scale.value - stageW.value) / 2)
    const maxY = Math.max(0, (frame.value.h * scale.value - stageH.value) / 2)
    ox.value = Math.min(maxX, Math.max(-maxX, ox.value))
    oy.value = Math.min(maxY, Math.max(-maxY, oy.value))
  }

  /**
   * Geometric zoom.
   * With coordinates it anchors on the cursor, so the content point under the cursor does not move; the transform origin is the centre of the image frame. o' = o*(s'/s) + (V-C)*(1-s'/s), where C is the stage centre, V the cursor and o the current offset.
  */
  function zoom(f, vx, vy) {
    const old = scale.value
    const next = Math.min(MAX_SCALE, Math.max(minScale.value, Math.round(old * f * 100) / 100))
    if (next === old) return
    if (vx != null && next > 1) {
      const cx = winW.value / 2
      const cy = centerY.value
      const k = next / old
      ox.value = Math.round(ox.value * k + (vx - cx) * (1 - k))
      oy.value = Math.round(oy.value * k + (vy - cy) * (1 - k))
    }
    scale.value = next
    clampOffset()
  }

  function onWheel(e) {
    e.preventDefault()
    zoom(e.deltaY < 0 ? ZOOM_FACTOR : 1 / ZOOM_FACTOR, e.clientX, e.clientY)
  }

  /** Pan with Shift plus an arrow key.
   * It only means anything once zoomed in, and the caller decides, because only it knows whether Shift is held. */
  function panBy(dx, dy) {
    ox.value += dx
    oy.value += dy
    clampOffset()
  }

  function onPointerDown(e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.size === 2) {
      // A second finger starts a pinch: record the starting distance, scale, offset and midpoint, and cancel the one-finger drag.
      const [a, b] = [...pointers.values()]
      dragging.value = false
      dragFrom = null
      pinching.value = true
      pinchFrom = {
        dist: Math.hypot(a.x - b.x, a.y - b.y),
        scale: scale.value,
        ox: ox.value,
        oy: oy.value,
        cx: (a.x + b.x) / 2,
        cy: (a.y + b.y) / 2,
      }
      return
    }
    if (pointers.size > 1 || scale.value <= 1) return
    dragging.value = true
    dragFrom = { x: e.clientX, y: e.clientY, ox: ox.value, oy: oy.value }
  }

  function onPointerMove(e) {
    if (!pointers.has(e.pointerId)) return
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pinchFrom && pointers.size >= 2) return pinchMove()
    if (!dragging.value || !dragFrom) return
    ox.value = dragFrom.ox + (e.clientX - dragFrom.x)
    oy.value = dragFrom.oy + (e.clientY - dragFrom.y)
    clampOffset()
  }

  /** Pinch zoom: the distance ratio times the starting scale, anchored on the midpoint between the fingers with the same formula as the wheel, and the midpoint tracks. */
  function pinchMove() {
    const [a, b] = [...pointers.values()]
    const dist = Math.hypot(a.x - b.x, a.y - b.y)
    if (!dist || !pinchFrom.dist) return
    const next = Math.min(MAX_SCALE, Math.max(minScale.value, pinchFrom.scale * (dist / pinchFrom.dist)))
    const k = next / pinchFrom.scale
    const cx = (a.x + b.x) / 2
    const cy = (a.y + b.y) / 2
    const scx = winW.value / 2
    const scy = centerY.value
    ox.value = pinchFrom.ox * k + (pinchFrom.cx - scx) * (1 - k) + (cx - pinchFrom.cx)
    oy.value = pinchFrom.oy * k + (pinchFrom.cy - scy) * (1 - k) + (cy - pinchFrom.cy)
    scale.value = next
    clampOffset()
  }

  function onPointerUp(e) {
    pointers.delete(e.pointerId)
    if (pointers.size < 2) {
      pinching.value = false
      pinchFrom = null
    }
    if (pointers.size === 1 && scale.value > 1) {
      // One finger left after a pinch: hand straight back to dragging.
      const [p] = [...pointers.values()]
      dragging.value = true
      dragFrom = { x: p.x, y: p.y, ox: ox.value, oy: oy.value }
      return
    }
    if (pointers.size !== 0) return
    dragging.value = false
    dragFrom = null
  }

  function onResize() {
    // An image sitting at the fit was never zoomed by hand, so a new window size re-takes the fit rather than keeping a scale that no longer fills the stage.
    const wasFitted = Math.abs(scale.value - minScale.value) < 1e-3
    winW.value = window.innerWidth
    winH.value = window.innerHeight
    if (wasFitted || scale.value < minScale.value) scale.value = minScale.value
    clampOffset()
  }

  onMounted(() => window.addEventListener('resize', onResize))
  onUnmounted(() => window.removeEventListener('resize', onResize))

  return {
    scale, dragging, pinching, gesturing,
    frameStyle, transform, insets,
    fitToStage, zoom, panBy, onWheel, onPointerDown, onPointerMove, onPointerUp,
  }
}
