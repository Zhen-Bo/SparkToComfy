/** The catalog and the current selection: which workflows exist, which one is chosen, what the parameters are and the size they resolve to. */

import { computed, reactive } from 'vue'

export const LORA_MAX = 5

export const catalog = reactive({
  // Catalog data, loaded by the API layer
  workflows: [],

  // Current selection.
  // The shape of params comes from the workflow declaration; each key is a control name.
  workflowId: null,
  params: {},
  // Deep copy of params at the moment of a restore.
  // The panel uses it to mark which fields have since been edited.
  // It is null when nothing was restored.
  restoredBaseline: null,
  seedLocked: false,
})

function controlsOf(workflowId) {
  const wf = catalog.workflows.find((w) => w.id === workflowId)
  return { ...(wf?.parameters?.basic ?? {}), ...(wf?.parameters?.advanced ?? {}) }
}

export const workflow = computed(() => catalog.workflows.find((w) => w.id === catalog.workflowId) ?? null)
export const controls = computed(() => controlsOf(catalog.workflowId))
export const constraints = computed(() => ({
  stepsMax: controls.value.steps?.max ?? 50,
  cfgMax: controls.value.cfg?.max ?? 7,
}))

/**
 * Width and height are looked up in the preset table and swapped when landscape is true.
 * The frontend never sends dimensions itself.
 * An unknown preset always returns null.
 * The preset keys come from config/size.yaml on the backend, so a rename or a replaced workflow leaves old history unresolvable.
 * Returning 1x1 there would be printed as fact, both as the size readout and as a square viewfinder, which is worse than a visible blank.
 * This is an audit path, and being exact is its entire reason to exist.
*/
export function sizeOf(workflowId, size) {
  const preset = controlsOf(workflowId).size?.presets?.[size?.preset]
  if (!preset) return null
  const { width, height } = size.highres ? preset.highres : preset.standard
  return size.landscape ? { width: height, height: width } : { width, height }
}

// The current selection always resolves, since its presets come from the same declaration.
// The ?? only keeps the stage alive during the startup gap.
export const currentDims = computed(() => sizeOf(catalog.workflowId, catalog.params.size) ?? { width: 1, height: 1 })
/* That 1x1 above exists so the viewfinder has numbers to draw a box with; it is not a fact.
   This flag decides whether the readout prints at all, because showing 1 x 1 during the startup gap, or when a workflow has no matching preset, would print a lie.
   Same reason sizeOf returns null. */
export const dimsKnown = computed(() => sizeOf(catalog.workflowId, catalog.params.size) !== null)

/** Upscale factor.
    It exists only when the workflow declares an upscale control, and is 1 otherwise.
    The real output size multiplies both base dimensions by the factor, which leaves the aspect ratio and the viewfinder shape untouched. */
export const upscaleFactor = computed(() => Math.max(1, Number(catalog.params.upscale ?? 1)))
export const outputDims = computed(() => {
  const { width, height } = currentDims.value
  const k = upscaleFactor.value
  return { width: Math.round(width * k), height: Math.round(height * k) }
})

function defaultOf(ctl) {
  if (ctl.type === 'lora') return []
  if (ctl.type === 'size') return { preset: Object.keys(ctl.presets)[0], highres: false, landscape: false }
  if (ctl.default != null) return ctl.default
  if (ctl.type === 'dropdown') return Object.keys(ctl.options)[0]
  return ctl.type === 'multiline' ? '' : 0
}

export function selectWorkflow(id) {
  if (!catalog.workflows.some((w) => w.id === id)) return
  catalog.workflowId = id
  catalog.restoredBaseline = null
  catalog.params = Object.fromEntries(
    Object.entries(controlsOf(id)).map(([name, ctl]) => [name, defaultOf(ctl)]),
  )
}
