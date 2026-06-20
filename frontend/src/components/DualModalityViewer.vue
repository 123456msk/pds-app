<template>
  <el-dialog v-model="dialogVisible" fullscreen class="viewer-dialog" destroy-on-close @closed="resetViewer">
    <template #header>
      <div class="viewer-titlebar">
        <div><strong>双模态联合阅片器</strong><span>{{ patientLabel }}</span></div>
        <div class="viewer-legend"><span class="legend-pz"></span>PZ 外周带 <span class="legend-tz"></span>TZ 移行带</div>
      </div>
    </template>

    <div v-loading="loading" element-loading-text="正在加载 MRI / PET 及 PZ、TZ 掩膜" class="viewer-body">
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <div v-else class="viewer-grid">
        <section class="viewer-pane">
          <header><div><b>MRI T2W</b><span>{{ mriSlice + 1 }} / {{ mriVolume?.dimensions?.[2] || 0 }}</span></div><div class="viewer-controls"><el-checkbox v-model="showMriPz">PZ</el-checkbox><el-checkbox v-model="showMriTz">TZ</el-checkbox></div></header>
          <div class="canvas-stage" @wheel.prevent="changeSlice('mri', $event.deltaY > 0 ? 1 : -1)"><canvas ref="mriCanvas"></canvas><span v-if="!mriVolume" class="empty-view">暂无 MRI 结果</span></div>
          <footer><el-button :icon="ArrowLeft" circle @click="changeSlice('mri', -1)" /><el-slider v-model="mriSlice" :min="0" :max="Math.max(0, (mriVolume?.dimensions?.[2] || 1) - 1)" :show-tooltip="false" /><el-button :icon="ArrowRight" circle @click="changeSlice('mri', 1)" /></footer>
        </section>

        <section class="viewer-pane">
          <header><div><b>PSMA PET</b><span>{{ petSlice + 1 }} / {{ petVolume?.dimensions?.[2] || 0 }}</span></div><div class="viewer-controls"><el-checkbox v-model="showPetPz">PZ</el-checkbox><el-checkbox v-model="showPetTz">TZ</el-checkbox></div></header>
          <div class="canvas-stage" @wheel.prevent="changeSlice('pet', $event.deltaY > 0 ? 1 : -1)"><canvas ref="petCanvas"></canvas><span v-if="!petVolume" class="empty-view">暂无 PET 结果</span></div>
          <footer><el-button :icon="ArrowLeft" circle @click="changeSlice('pet', -1)" /><el-slider v-model="petSlice" :min="0" :max="Math.max(0, (petVolume?.dimensions?.[2] || 1) - 1)" :show-tooltip="false" /><el-button :icon="ArrowRight" circle @click="changeSlice('pet', 1)" /></footer>
        </section>
      </div>

      <div v-if="!error" class="viewer-settings">
        <span>掩膜透明度</span><el-slider v-model="maskOpacity" :min="10" :max="90" :format-tooltip="value => value + '%'" />
        <span>亮度</span><el-slider v-model="brightness" :min="50" :max="180" :format-tooltip="value => value + '%'" />
        <el-button :icon="Refresh" @click="resetDisplay">重置显示</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { ArrowLeft, ArrowRight, Refresh } from '@element-plus/icons-vue';
import { loadNifti } from '../composables/useNiftiVolume';
import { resultFileUrl } from '../api/casePreparation';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  caseId: { type: String, default: '' },
  patient: { type: Object, default: () => ({}) },
});
const emit = defineEmits(['update:modelValue']);
const dialogVisible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) });
const patientLabel = computed(() => [props.patient?.name, props.patient?.age != null ? `${props.patient.age} 岁` : '', props.patient?.psa != null ? `PSA ${props.patient.psa} ng/ml` : ''].filter(Boolean).join(' · '));

const loading = ref(false);
const error = ref('');
const mriCanvas = ref(null);
const petCanvas = ref(null);
const mriVolume = ref(null);
const petVolume = ref(null);
const mriPz = ref(null);
const mriTz = ref(null);
const petPz = ref(null);
const petTz = ref(null);
const mriSlice = ref(0);
const petSlice = ref(0);
const showMriPz = ref(true);
const showMriTz = ref(true);
const showPetPz = ref(true);
const showPetTz = ref(true);
const maskOpacity = ref(58);
const brightness = ref(100);

function renderCanvas(canvas, volume, pz, tz, slice, showPz, showTz, rotate = false) {
  if (!canvas || !volume) return;
  const [nx, ny, nz] = volume.dimensions;
  const safeSlice = Math.max(0, Math.min(nz - 1, slice));
  const outputWidth = rotate ? ny : nx;
  const outputHeight = rotate ? nx : ny;
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const context = canvas.getContext('2d');
  const image = context.createImageData(outputWidth, outputHeight);
  const offset = safeSlice * nx * ny;
  let minimum = Infinity;
  let maximum = -Infinity;
  for (let index = 0; index < nx * ny; index += 1) {
    const value = volume.data[offset + index];
    if (Number.isFinite(value) && value !== 0) {
      minimum = Math.min(minimum, value);
      maximum = Math.max(maximum, value);
    }
  }
  if (!Number.isFinite(minimum) || maximum <= minimum) { minimum = 0; maximum = 1; }
  const alpha = maskOpacity.value / 100;
  const level = brightness.value / 100;
  for (let y = 0; y < ny; y += 1) {
    for (let x = 0; x < nx; x += 1) {
      const sourceIndex = offset + y * nx + x;
      let intensity = ((volume.data[sourceIndex] - minimum) / (maximum - minimum)) * 255 * level;
      intensity = Math.max(0, Math.min(255, intensity));
      let red = intensity;
      let green = intensity;
      let blue = intensity;
      if (showPz && pz?.data[sourceIndex] > 0) {
        red = red * (1 - alpha) + 14 * alpha;
        green = green * (1 - alpha) + 165 * alpha;
        blue = blue * (1 - alpha) + 233 * alpha;
      }
      if (showTz && tz?.data[sourceIndex] > 0) {
        red = red * (1 - alpha) + 245 * alpha;
        green = green * (1 - alpha) + 158 * alpha;
        blue = blue * (1 - alpha) + 11 * alpha;
      }
      const outputX = rotate ? ny - 1 - y : x;
      const outputY = rotate ? x : y;
      const pixel = (outputY * outputWidth + outputX) * 4;
      image.data[pixel] = red;
      image.data[pixel + 1] = green;
      image.data[pixel + 2] = blue;
      image.data[pixel + 3] = 255;
    }
  }
  context.putImageData(image, 0, 0);
}

function renderAll() {
  renderCanvas(mriCanvas.value, mriVolume.value, mriPz.value, mriTz.value, mriSlice.value, showMriPz.value, showMriTz.value, true);
  renderCanvas(petCanvas.value, petVolume.value, petPz.value, petTz.value, petSlice.value, showPetPz.value, showPetTz.value, false);
}

async function loadViewer() {
  if (!props.caseId) return;
  loading.value = true;
  error.value = '';
  try {
    const file = name => loadNifti(resultFileUrl(props.caseId, name));
    [mriVolume.value, mriPz.value, mriTz.value, petVolume.value, petPz.value, petTz.value] = await Promise.all([
      file('mri.nii.gz'), file('mripz_mask.nii.gz'), file('mritz_mask.nii.gz'),
      file('pet.nii.gz'), file('petpz_mask.nii.gz'), file('pettz_mask.nii.gz'),
    ]);
    mriSlice.value = Math.floor(mriVolume.value.dimensions[2] / 2);
    petSlice.value = Math.floor(petVolume.value.dimensions[2] / 2);
    await nextTick();
    renderAll();
  } catch (failure) {
    error.value = failure.message || '阅片器加载失败。';
  } finally {
    loading.value = false;
  }
}

function changeSlice(modality, delta) {
  const value = modality === 'mri' ? mriSlice : petSlice;
  const volume = modality === 'mri' ? mriVolume.value : petVolume.value;
  if (!volume) return;
  value.value = Math.max(0, Math.min(volume.dimensions[2] - 1, value.value + delta));
}
function resetDisplay() { maskOpacity.value = 58; brightness.value = 100; showMriPz.value = true; showMriTz.value = true; showPetPz.value = true; showPetTz.value = true; }
function resetViewer() { mriVolume.value = null; petVolume.value = null; mriPz.value = null; mriTz.value = null; petPz.value = null; petTz.value = null; error.value = ''; }

watch(() => props.modelValue, visible => { if (visible) loadViewer(); });
watch([mriSlice, petSlice, showMriPz, showMriTz, showPetPz, showPetTz, maskOpacity, brightness], () => nextTick(renderAll));
</script>