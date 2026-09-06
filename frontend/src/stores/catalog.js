import { computed, reactive } from 'vue'

export const LORA_MAX = 10

export const catalog = reactive({
  workflows: [],

  // The shape of params comes from the workflow declaration; each key is a control name.
  workflowId: null,
  params: {},
  // Snapshot for marking edits made after a history restore; null when no baseline exists.
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

// Old history may reference removed presets; return null rather than inventing dimensions.
export function sizeOf(workflowId, size) {
  const preset = controlsOf(workflowId).size?.presets?.[size?.preset]
  if (!preset) return null
  const { width, height } = size.highres ? preset.highres : preset.standard
  return size.landscape ? { width: height, height: width } : { width, height }
}

// The 1x1 fallback is for layout only; use dimsKnown before displaying dimensions.
export const currentDims = computed(() => sizeOf(catalog.workflowId, catalog.params.size) ?? { width: 1, height: 1 })
export const dimsKnown = computed(() => sizeOf(catalog.workflowId, catalog.params.size) !== null)

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
