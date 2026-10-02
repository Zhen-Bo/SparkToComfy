import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

export const MAX_SCALE = 4
export const ZOOM_FACTOR = 1.12
export const PAN_STEP = 40 // pan step in px for Shift plus an arrow key
const EDGE = 16 // minimum distance between the image frame and each window edge
const NARROW = 960 // below this the layout is the phone one (MobileStudioView takes over at the same line)
const NARROW_SIDE = 8
const BAR_GAP = 8 // space between the image and a bar, so the frame's corner brackets stay visible
const TOP_BAR = 20 + 44 + BAR_GAP // the 44px top bar sits 20px from the edge

/**
 * topClear: px from either top corner the hint and action bar occupy; the image only gives up the top band when it would reach them.
 * bottomBar: measured height of the phone thumbnail strip, which grows when a scrollbar appears.
 */
export function useZoomPan(dims, { topClear, bottomBar }) {
  const scale = ref(1)
  const ox = ref(0)
  const oy = ref(0)
  const dragging = ref(false)
  const pinching = ref(false)
  const winW = ref(window.innerWidth)
  const winH = ref(window.innerHeight)
  let dragFrom = null
  const pointers = new Map() // active pointers, pointerId to coordinates, used by the pinch gesture
  let pinchFrom = null

  const isLandscape = computed(() => dims.value.width > dims.value.height)

  const narrow = computed(() => winW.value < NARROW)
  const side = computed(() => (narrow.value ? NARROW_SIDE : EDGE))
  /* Two ways to keep the image off the corner controls; take whichever shows it larger:
     below the top bar at full width, or at full height narrowed to the gap between the corners. */
  const layout = computed(() => {
    const a = dims.value.width / dims.value.height
    const fullW = winW.value - side.value * 2
    const fit = (w, top, bottom) => ({ stageW: w, top, bottom, shown: Math.min(w, (winH.value - top - bottom) * a) })
    const bottom = narrow.value ? bottomBar.value + BAR_GAP : EDGE
    const below = fit(fullW, TOP_BAR, bottom)
    const between = fit(Math.min(fullW, winW.value - topClear.value * 2), EDGE, bottom)
    return between.shown >= below.shown ? between : below
  })
  const insets = computed(() => ({ top: layout.value.top, bottom: layout.value.bottom }))

  const stageW = computed(() => layout.value.stageW)
  const stageH = computed(() => winH.value - insets.value.top - insets.value.bottom)
  const centerY = computed(() => (winH.value + insets.value.top - insets.value.bottom) / 2)

  const frame = computed(() => {
    const a = dims.value.width / dims.value.height
    return isLandscape.value ? { w: stageW.value, h: stageW.value / a } : { w: stageH.value * a, h: stageH.value }
  })
  const frameStyle = computed(() => ({ width: `${frame.value.w}px`, height: `${frame.value.h}px` }))

  // Round the fit down; rounding up could push the image past the available space.
  const minScale = computed(() => Math.min(1, Math.floor(Math.min(stageW.value / frame.value.w, stageH.value / frame.value.h) * 100) / 100))

  const transform = computed(() => `translate(${ox.value}px, ${oy.value}px) scale(${scale.value})`)

  // The caller disables backdrop blur while gesturing to avoid filtering every moving frame.
  const gesturing = computed(() => dragging.value || pinching.value)

  function fitToStage() {
    scale.value = minScale.value
    ox.value = 0
    oy.value = 0
  }

  // Stop panning at image edges; dimensions smaller than the stage stay centred.
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

  // Preserve fit mode when the stage changes (window, top bar, strip) while retaining a manual zoom when possible.
  watch(minScale, (now, before) => {
    if (Math.abs(scale.value - before) < 1e-3 || scale.value < now) scale.value = now
    clampOffset()
  })

  function onResize() {
    winW.value = window.innerWidth
    winH.value = window.innerHeight
  }

  onMounted(() => window.addEventListener('resize', onResize))
  onUnmounted(() => window.removeEventListener('resize', onResize))

  return {
    scale, dragging, pinching, gesturing,
    frameStyle, transform, insets,
    fitToStage, zoom, panBy, onWheel, onPointerDown, onPointerMove, onPointerUp,
  }
}
