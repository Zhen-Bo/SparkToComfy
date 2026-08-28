<script setup>
/**
 * The component overview at /playground, laid out as a vertical ledger.
 * Every specimen mounts the real component from src/components, so changing any component's style or behaviour changes the workspace and this wall at once: one source.
 * Rows never drive each other.
 * The generate button only plays its own busy state through the demo prop, and the preview progress runs from an independent loop below without going through generate() or leaving a history card.
*/
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { catalog, constraints, currentDims, selectWorkflow, workflow } from '@/stores/catalog'
import { locked } from '@/stores/run'
import { run } from '@/stores/run'
import Slider from '@/components/ui/Slider.vue'
import Textarea from '@/components/ui/Textarea.vue'
import ParamSlider from '@/components/obs/ParamSlider.vue'
import SeedControl from '@/components/obs/SeedControl.vue'
import ObsDropdown from '@/components/obs/ObsDropdown.vue'
import RatioSelector from '@/components/obs/RatioSelector.vue'
import LoraField from '@/components/obs/LoraField.vue'
import LoraPickerDialog from '@/components/obs/LoraPickerDialog.vue'
import PanelTabs from '@/components/obs/PanelTabs.vue'
import GenerateButton from '@/components/obs/GenerateButton.vue'
import StagePlate from '@/components/obs/StagePlate.vue'
import QueueSlots from '@/components/obs/QueueSlots.vue'
import HistoryRail from '@/components/obs/HistoryRail.vue'
import ThemeSwitcher from '@/components/obs/ThemeSwitcher.vue'

/* The workspace is an app-style page that never scrolls, while this overview is a long page, so body scrolling is restored while it is mounted (see style.css). */
document.documentElement.dataset.route = 'playground'

/* The preview loop demonstrates four phases: queue 07 down to 01, preparing for 1.4s, progress 0 to 100, an upscale sweep for 2.4s, then a hold and a restart.
   It drives the real StagePlate by writing run.busy, phase, queueAhead and progress directly, without going through generate() and without leaving a history card.

   It never starts while a real job is running: the demo would cover that job's screen, and the teardown reset to phase idle and busy false would show a running job as idle. driving records that this loop is the one that took the stage, so only it resets. */
let stageTimer = null
let driving = false
function stageLoop() {
  if (run.busy && !driving) return // a real job is running, so the demo stands aside
  driving = true
  let a = 7
  run.busy = true
  run.phase = 'queued'
  run.queueAhead = 7
  stageTimer = setInterval(() => {
    a -= 1
    run.queueAhead = a
    if (a <= 0) {
      clearInterval(stageTimer)
      run.phase = 'preparing'
      stageTimer = setTimeout(runGenPhase, 1400)
    }
  }, 650)
}
function runGenPhase() {
  run.phase = 'generating'
  run.queueAhead = null
  let v = 0
  run.progress = { step: 0, total: 28 }
  stageTimer = setInterval(() => {
    v = Math.min(100, v + 4 + Math.random() * 5)
    run.progress = { step: Math.round((v / 100) * 28), total: 28 }
    if (v >= 100) {
      clearInterval(stageTimer)
      stageTimer = setTimeout(runUpPhase, 420)
    }
  }, 110)
}
function runUpPhase() {
  run.phase = 'upscaling'
  run.progress = null
  stageTimer = setTimeout(() => {
    run.phase = 'idle'
    run.busy = false
    stageTimer = setTimeout(stageLoop, 1600)
  }, 2400)
}

/* The queue-slots specimen runs 07 down to 01 and then ready from local state, never the store, matching the display rule of the preview row. */
const qsAhead = ref(7)
const qsReady = ref(false)
const qsEta = computed(() => {
  const s = qsAhead.value * 15
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})
let qsTimer = null
function qsLoop() {
  qsAhead.value = 7
  qsReady.value = false
  qsTimer = setInterval(() => {
    if (qsAhead.value > 0) {
      qsAhead.value -= 1
      if (qsAhead.value === 0) {
        clearInterval(qsTimer)
        qsReady.value = true
        qsTimer = setTimeout(qsLoop, 1400)
      }
    }
  }, 650)
}
onMounted(() => { stageLoop(); qsLoop() })
onUnmounted(() => {
  delete document.documentElement.dataset.route
  for (const t of [stageTimer, qsTimer]) { clearInterval(t); clearTimeout(t) }
  if (!driving) return // this loop did not take the stage, so leave it alone
  driving = false
  run.busy = false
  run.phase = 'idle'
  run.queueAhead = null
  run.progress = null
})

/* Demo state owned by the specimens themselves and kept out of the store: the bare slider, the tab demo and the picker open state. */
const { t, tm, rt } = useI18n()
const bareSlider = ref([40])
const demoTab = ref('create')
const loraDialogOpen = ref(false)

const workflowItems = computed(() =>
  catalog.workflows.map((w) => ({ value: w.id, label: w.name, desc: w.desc })),
)
const orientation = computed(() => {
  const { width, height } = currentDims.value
  return width === height ? t('playground.square') : width > height ? t('playground.landscape') : t('playground.portrait')
})

/* The catalog: one row per file, with no extra rows for other uses of the same component.
   Families are ordered ui/ first and obs/ second. name, meta and family are all i18n keys under playground.*; family doubles as the group key, so the order of the fam* keys is the family order. */
const CATALOG = [
  { key: 'slider', tag: 'ui/Slider.vue', nameKey: 'playground.catalog.slider.name', family: 'famUi', metaKey: 'playground.catalog.slider.meta' },
  { key: 'textarea', tag: 'ui/Textarea.vue', nameKey: 'playground.catalog.textarea.name', family: 'famUi', metaKey: 'playground.catalog.textarea.meta' },
  { key: 'dialog', tag: 'ui/Dialog.vue ・ LoraPickerDialog', nameKey: 'playground.catalog.dialog.name', family: 'famUi', metaKey: 'playground.catalog.dialog.meta' },
  { key: 'params', tag: 'obs/ParamSlider.vue', nameKey: 'playground.catalog.params.name', family: 'famObs', metaKey: 'playground.catalog.params.meta' },
  { key: 'seed', tag: 'obs/SeedControl.vue', nameKey: 'playground.catalog.seed.name', family: 'famObs', metaKey: 'playground.catalog.seed.meta' },
  { key: 'dropdown', tag: 'obs/ObsDropdown.vue', nameKey: 'playground.catalog.dropdown.name', family: 'famObs', metaKey: 'playground.catalog.dropdown.meta' },
  { key: 'ratio', tag: 'obs/RatioSelector.vue', nameKey: 'playground.catalog.ratio.name', family: 'famObs', metaKey: 'playground.catalog.ratio.meta' },
  { key: 'lora', tag: 'obs/LoraField.vue', nameKey: 'playground.catalog.lora.name', family: 'famObs', metaKey: 'playground.catalog.lora.meta' },
  { key: 'tabs', tag: 'obs/PanelTabs.vue', nameKey: 'playground.catalog.tabs.name', family: 'famObs', metaKey: 'playground.catalog.tabs.meta' },
  { key: 'qs', tag: 'obs/QueueSlots.vue', nameKey: 'playground.catalog.qs.name', family: 'famObs', metaKey: 'playground.catalog.qs.meta' },
  { key: 'cta', tag: 'obs/GenerateButton.vue', nameKey: 'playground.catalog.cta.name', family: 'famObs', metaKey: 'playground.catalog.cta.meta' },
  { key: 'stage', tag: 'obs/StagePlate.vue', nameKey: 'playground.catalog.stage.name', family: 'famPreview', metaKey: 'playground.catalog.stage.meta' },
  { key: 'history', tag: 'obs/HistoryRail.vue', nameKey: 'playground.catalog.history.name', family: 'famPreview', metaKey: 'playground.catalog.history.meta' },
]

/* The interaction checklists live under playground.chk.*, as array messages: tm fetches them and rt renders each line into a string. */
const chkOf = (key) => tm(`playground.chk.${key}`).map((line) => rt(line))

const FAMS = [...new Set(CATALOG.map((c) => c.family))]
</script>

<template>
  <div class="obs-grain pg">
    <header class="hero">
      <span class="brandbox">
        <span class="brand" translate="no">SparkToComfy</span>
        <span class="brandsub">{{ t('playground.subtitle') }}</span>
      </span>
      <h1>{{ t('playground.title') }}</h1>
      <span class="way">{{ t('playground.way') }}</span>
      <span class="heroact">
        <RouterLink class="backlink" to="/">{{ t('playground.back') }}</RouterLink>
        <ThemeSwitcher />
      </span>
    </header>

    <nav class="famnav" :aria-label="t('playground.famNavAria')">
      <div class="famnav-in">
        <a v-for="(f, i) in FAMS" :key="f" :href="`#sec-${i}`">{{ t(`playground.${f}`) }}</a>
        <span class="cnt">{{ t('playground.count', { n: CATALOG.length }) }}</span>
      </div>
    </nav>

    <main class="wall">
      <section v-for="(f, i) in FAMS" :key="f" :id="`sec-${i}`" class="sec">
        <h2 class="obs-label seclabel">{{ t(`playground.${f}`) }}</h2>
        <div v-for="c in CATALOG.filter((x) => x.family === f)" :key="c.key" class="row">
          <div class="ri">
            <span class="tag" translate="no">{{ c.tag }}</span>
            <span class="name">{{ t(c.nameKey) }}</span>
            <span class="meta">{{ t(c.metaKey) }}</span>
            <span v-if="chkOf(c.key).length" class="chk"><i v-for="line in chkOf(c.key)" :key="line">{{ line }}</i></span>
          </div>

          <div class="rb">
              <div v-if="c.key === 'slider'" class="band">
              <Slider v-model="bareSlider" :aria-label="t('playground.sliderAria')" />
            </div>

            <!-- ui/Textarea writes the store directly, so the workspace prompt stays in sync -->
            <div v-else-if="c.key === 'textarea'" class="band wide">
              <Textarea :model-value="catalog.params.positive ?? ''" @update:model-value="catalog.params.positive = $event" :rows="3" :aria-label="t('playground.positivePrompt')" translate="no" />
            </div>

              <div v-else-if="c.key === 'dialog'" class="band" style="max-width: 340px">
              <button type="button" class="ghostcta obs-tr" @click="loraDialogOpen = true">{{ t('playground.openPicker') }}</button>
              <LoraPickerDialog v-model:open="loraDialogOpen" />
            </div>

              <div v-else-if="c.key === 'params'" class="band">
              <div class="sublabel">{{ t('playground.steps') }}</div>
              <ParamSlider :model-value="catalog.params.steps ?? 0" @update:model-value="catalog.params.steps = $event" :min="0" :max="constraints.stepsMax" :step="1" :label="t('playground.steps')" />
              <div style="height: 14px"></div>
              <div class="sublabel">CFG</div>
              <ParamSlider :model-value="catalog.params.cfg ?? 0" @update:model-value="catalog.params.cfg = $event" :min="0" :max="constraints.cfgMax" :step="0.1" :decimals="1" label="CFG" />
            </div>

              <div v-else-if="c.key === 'seed'" class="band">
              <SeedControl />
            </div>

              <div v-else-if="c.key === 'dropdown'" class="band">
              <ObsDropdown :items="workflowItems" :model-value="catalog.workflowId" :label="t('panel.workflow')" @change="(id) => !locked && selectWorkflow(id)" />
              <div class="obs-hint" translate="no">{{ workflow?.desc }}</div>
            </div>

              <div v-else-if="c.key === 'ratio'" class="band">
              <RatioSelector />
              <div class="obs-hint" translate="no">{{ currentDims.width }} × {{ currentDims.height }} ・ {{ orientation }}</div>
            </div>

              <div v-else-if="c.key === 'lora'" class="band wide">
              <LoraField />
            </div>

            <!-- obs/PanelTabs, with a matching tabpanel so the aria chain is complete -->
            <div v-else-if="c.key === 'tabs'" class="band" style="max-width: 340px">
              <PanelTabs v-model="demoTab" id-base="pg" />
              <div
                :id="`pg-tabpanel-${demoTab}`"
                :aria-labelledby="`pg-tab-${demoTab}`"
                role="tabpanel"
                class="obs-hint"
              >{{ t('playground.tabsNote', { tab: t(`tabs.${demoTab}`) }) }}</div>
            </div>

            <!-- obs/QueueSlots, driven locally from queue to ready; the upscale sweep is in the four-phase preview demo -->
            <div v-else-if="c.key === 'qs'" class="band" style="max-width: 340px">
              <div class="qswrap"><QueueSlots :ahead="qsAhead" :ready="qsReady" :eta="qsEta" /></div>
            </div>

            <!-- obs/GenerateButton in demo mode: it plays its own busy state only, starting no generation and touching no other row -->
            <div v-else-if="c.key === 'cta'" class="band">
              <GenerateButton demo />
              <div class="obs-hint">{{ t('playground.ctaNote') }}</div>
            </div>

            <!-- obs/StagePlate in a fixed-height container, with the frame ratio following the size row -->
            <div v-else-if="c.key === 'stage'" class="band" style="max-width: 340px">
              <div class="stagewrap"><StagePlate /></div>
            </div>

              <div v-else-if="c.key === 'history'" class="band" style="max-width: 266px">
              <div class="histwrap"><HistoryRail open /></div>
              <!-- Collapsed: the entry button sits outside the rail, on the stage side, so a box standing in for the stage background is needed to see it -->
              <div class="histbtnwrap"><HistoryRail /></div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
/* The ledger layout uses the same CSS variables as the rest of the app, so theme switching works here without anything extra */
.pg { min-height: 100vh; }

.hero { max-width: 1120px; margin: 0 auto; padding: 26px 28px 18px; display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }
.brandbox { display: flex; flex-direction: column; gap: 3px; }
.brand { font-family: 'Chakra Petch', 'Taipei Sans TC', sans-serif; font-size: 15px; font-weight: 700; letter-spacing: .06em; color: hsl(var(--foreground)); }
.brandsub { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 9px; letter-spacing: .14em; color: hsl(var(--ink-faint)); }
.hero h1 { font-size: 22px; font-weight: 900; letter-spacing: .03em; }
.way { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 10px; letter-spacing: .08em; color: hsl(var(--ink-faint)); }
.heroact { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.backlink { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 10.5px; letter-spacing: .1em; color: hsl(var(--muted-foreground)); text-decoration: none; }
.backlink:hover { color: hsl(var(--amber-bright)); }

.famnav { position: sticky; top: 0; z-index: 20; background: hsl(var(--dome) / .86); backdrop-filter: blur(10px); border-bottom: 1px solid hsl(var(--hairline)); }
.famnav-in { max-width: 1120px; margin: 0 auto; padding: 11px 28px; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.famnav a { padding: 5px 12px; border-radius: 4px; border: 1px solid hsl(var(--hairline)); background: hsl(var(--inset)); font-size: 11.5px; font-weight: 600; color: hsl(var(--muted-foreground)); text-decoration: none; letter-spacing: .05em; }
.famnav a:hover { border-color: hsl(var(--edgeline)); color: hsl(var(--foreground)); }
.cnt { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 9px; color: hsl(var(--ink-faint)); margin-left: auto; letter-spacing: .08em; }

.wall { max-width: 1120px; margin: 0 auto; padding: 0 28px 140px; }
/* scroll-margin 56px: the sticky .famnav is about 56px tall and would cover a section heading after an anchor jump */
.sec { margin-top: 30px; scroll-margin-top: 56px; }
.seclabel { font-size: 14px; margin-bottom: 0; }

/* Ledger row: a fixed information column on the left, a full-width interaction area right */
.row { display: grid; grid-template-columns: 236px minmax(0, 1fr); gap: 26px; padding: 18px 0 20px; border-bottom: 1px solid hsl(var(--hairline)); }
.row:last-child { border-bottom: 0; }
.ri { display: flex; flex-direction: column; gap: 5px; padding-top: 2px; }
.ri .tag { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 10px; letter-spacing: .08em; color: hsl(var(--amber-bright)); }
.ri .name { font-size: 14px; font-weight: 700; letter-spacing: .04em; }
.ri .meta { font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 9.5px; line-height: 1.8; letter-spacing: .03em; color: hsl(var(--ink-faint)); }
.ri .chk { margin-top: 8px; font-family: 'Chivo Mono', 'Taipei Sans TC', monospace; font-size: 9px; letter-spacing: .06em; color: hsl(var(--muted-foreground)); display: flex; flex-direction: column; gap: 3px; }
.ri .chk i { font-style: normal; }
.ri .chk i::before { content: '▸ '; color: hsl(var(--amber-dim)); }

.rb { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.band { max-width: 520px; width: 100%; }
.band.wide { max-width: 680px; }
.sublabel { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; font-size: 12.5px; font-weight: 700; letter-spacing: .1em; color: hsl(var(--foreground)); }

/* Picker trigger: the CTA shape in a quiet outline version */
.ghostcta { width: 100%; padding: 11px 0; border: 1px solid hsl(var(--hairline)); border-radius: 6px; background: transparent; color: hsl(var(--muted-foreground)); font-size: 12.5px; font-weight: 400; letter-spacing: .04em; cursor: pointer; }
.ghostcta:hover { border-color: hsl(var(--edgeline)); color: hsl(var(--foreground)); }

/* Preview and history specimens sit in fixed-height containers so each component adapts to the space available */
.stagewrap { display: flex; height: 380px; border: 1px solid hsl(var(--hairline)); border-radius: 4px; overflow: hidden; }
.stagewrap > * { flex: 1; min-width: 0; }
.qswrap { display: flex; justify-content: center; padding: 30px 0; border: 1px solid hsl(var(--hairline)); border-radius: 4px; background: hsl(var(--plate-bg)); }
/* The history rail keeps its own width so the collapse animation stays visible; the container does not stretch it */
.histbtnwrap { display: flex; justify-content: flex-end; height: 72px; margin-top: 10px; background: hsl(var(--dome)); border: 1px solid hsl(var(--hairline)); border-radius: 4px; align-items: stretch; }
.histwrap { display: flex; height: 460px; border: 1px solid hsl(var(--hairline)); border-radius: 4px; overflow: hidden; align-items: stretch; }

@media (max-width: 900px) {
  .row { grid-template-columns: 1fr; gap: 12px; }
  .ri { border-bottom: 1px dashed hsl(var(--hairline)); padding-bottom: 8px; }
}
</style>
