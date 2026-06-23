<template>
  <main class="editor-shell">
    <header class="editor-topbar">
      <div class="editor-brand">
        <span class="editor-brand-mark">P</span>
        <span>PDS 图像掩膜编辑器</span>
      </div>

      <div class="editor-toolbar">
        <label class="toolbar-button">
          添加数据
          <input type="file" accept=".nii,.nii.gz,.zip" multiple hidden @change="handleDataInput">
        </label>
        <span class="toolbar-divider"></span>
        <button
          v-for="tool in tools"
          :key="tool.mode"
          class="toolbar-button"
          :class="{ active: mode === tool.mode }"
          :disabled="tool.requiresMask && !selectedMask"
          type="button"
          @click="setMode(tool.mode)"
        >
          {{ tool.label }}
        </button>
        <button class="toolbar-button" type="button" :disabled="!undoStack.length" @click="undo">撤销</button>
        <button class="toolbar-button grid-toggle" :class="{ active: showGrid }" type="button" @click="showGrid = !showGrid; scheduleRenderAll()">
          网格
        </button>
        <span class="toolbar-divider"></span>
        <button class="toolbar-button save-button" type="button" :disabled="!masks.length" @click="saveChanges">
          {{ dirty ? '● 保存修改' : '✓ 已保存' }}
        </button>
        <button class="toolbar-button" type="button" :disabled="!selectedMask" @click="exportSelected">导出选中</button>
        <button class="toolbar-button" type="button" :disabled="!masks.length" @click="exportAll">导出全部</button>
      </div>

      <router-link class="back-link" to="/">返回诊断</router-link>
    </header>

    <section class="editor-workspace">
      <aside class="data-sidebar">
        <div class="sidebar-heading">
          <span>数据节点</span>
          <span>{{ images.length + masks.length }}</span>
        </div>
        <div class="data-tree">
          <div v-if="!images.length" class="empty-copy">可一次导入多个 NIfTI 文件或 ZIP 结果包。</div>
          <template v-else>
            <div
              v-for="volume in images"
              :key="volume.id"
              class="scene-group"
            >
              <div
                class="tree-item image-node"
                :class="{ selected: volume.id === activeImageId }"
                @click="activateImage(volume.id)"
              >
                <button
                  class="collapse-button"
                  :class="{ collapsed: collapsedImageIds.has(volume.id) }"
                  type="button"
                  :title="collapsedImageIds.has(volume.id) ? '展开' : '折叠'"
                  @click.stop="toggleImageGroup(volume.id)"
                >
                  <span></span>
                </button>
                <span class="node-chip image">I</span>
                <span class="node-main">
                  <strong>{{ stripExtension(volume.name) }}</strong>
                  <small>{{ volume.modalityHint }} · {{ volume.datatypeLabel }}</small>
                  <small>{{ volume.dim[1] }} × {{ volume.dim[2] }} × {{ volume.dim[3] }}</small>
                </span>
                <button class="icon-button remove" type="button" title="移除图像" @click.stop="removeImage(volume)">×</button>
              </div>
              <div v-show="!collapsedImageIds.has(volume.id)" class="group-masks">
                <div v-if="!masksForImage(volume.id).length" class="empty-copy compact">暂无关联 Mask</div>
                <div
                  v-for="mask in masksForImage(volume.id)"
                  :key="mask.id"
                  class="tree-item mask-node"
                  :class="{ selected: mask.id === selectedMaskId }"
                  @click="selectMask(mask)"
                >
                  <span class="tree-indent"></span>
                  <span class="node-chip" :style="{ background: mask.color }">M</span>
                  <span class="node-main">
                    <strong>{{ mask.name }}</strong>
                    <small>二值掩膜 · {{ mask.volume.toFixed(2) }} mL</small>
                  </span>
                  <button class="icon-button" type="button" :title="mask.visible ? '隐藏' : '显示'" @click.stop="toggleMask(mask)">
                    {{ mask.visible ? '●' : '○' }}
                  </button>
                  <button class="icon-button remove" type="button" title="移除" @click.stop="removeMask(mask)">×</button>
                </div>
              </div>
            </div>
          </template>
        </div>
      </aside>

      <section class="editor-center">
        <div class="volume-heading">
          <strong>{{ image ? stripExtension(image.name) : '未加载图像' }}</strong>
          <span>{{ image ? `${image.dim[1]} × ${image.dim[2]} × ${image.dim[3]}` : '--' }}</span>
        </div>

        <div
          class="viewport-grid"
          :class="{ 'drop-active': dragOver, 'has-fullscreen-plane': fullscreenPlane }"
          @dragenter.prevent="dragOver = true"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="handleDrop"
        >
          <div v-if="!image" class="editor-empty">
            将 NIfTI 文件或 ZIP 结果包拖入这里，或点击顶部“添加数据”。
          </div>

          <article
            v-show="image"
            class="plane-panel volume-3d"
            :class="{ fullscreen: fullscreenPlane === 'volume-3d', concealed: fullscreenPlane && fullscreenPlane !== 'volume-3d' }"
          >
            <header class="plane-header">
              <span>3D 掩膜视图</span>
              <div class="plane-actions">
                <button type="button" title="复位视角" @click="reset3DView">↺</button>
                <button type="button" :title="fullscreenPlane === 'volume-3d' ? '退出全屏' : '局部全屏'" @click="togglePlaneFullscreen('volume-3d')">
                  {{ fullscreenPlane === 'volume-3d' ? '↙' : '⛶' }}
                </button>
              </div>
            </header>
            <div ref="threeContainer" class="three-stage">
              <div v-if="!visibleMasksForActiveImage.length" class="three-empty">显示 Mask 后生成三维表面</div>
              <div class="orientation-cube">
                <span class="top">S</span>
                <span class="bottom">I</span>
                <span class="left">R</span>
                <span class="right">L</span>
                <span class="center">P</span>
              </div>
            </div>
            <footer class="three-footer">左键旋转 · 滚轮缩放 · 右键平移</footer>
          </article>

          <article
            v-for="plane in planeList"
            v-show="image"
            :key="plane.key"
            class="plane-panel"
            :class="[plane.key, { fullscreen: fullscreenPlane === plane.key, concealed: fullscreenPlane && fullscreenPlane !== plane.key }]"
          >
            <header class="plane-header">
              <span>{{ plane.label }}</span>
              <div class="plane-actions">
                <button type="button" title="缩小" @click="zoomPlane(plane.key, -0.25)">−</button>
                <span>{{ Math.round(zooms[plane.key] * 100) }}%</span>
                <button type="button" title="放大" @click="zoomPlane(plane.key, 0.25)">+</button>
                <button type="button" title="重置缩放" @click="resetPlaneZoom(plane.key)">↺</button>
                <button type="button" :title="fullscreenPlane === plane.key ? '退出全屏' : '局部全屏'" @click="togglePlaneFullscreen(plane.key)">
                  {{ fullscreenPlane === plane.key ? '↙' : '⛶' }}
                </button>
              </div>
            </header>

            <div class="canvas-stage">
              <canvas
                :ref="element => setCanvasRef(plane.key, element)"
                @mousedown="handleCanvasDown($event, plane.key)"
                @mousemove="handleCanvasMove($event, plane.key)"
                @dblclick="locateFromCanvas($event, plane.key)"
                @wheel.prevent="handlePlaneWheel($event, plane.key)"
              ></canvas>
              <span class="orientation-label">{{ plane.orientation }}</span>
            </div>

            <footer class="plane-footer">
              <input
                type="range"
                min="0"
                :max="planeMax(plane.key)"
                :value="planeSlice(plane.key)"
                @input="setPlaneSlice(plane.key, Number($event.target.value))"
              >
              <span>{{ planeSlice(plane.key) + 1 }} / {{ planeMax(plane.key) + 1 }}</span>
            </footer>
          </article>
        </div>
      </section>

      <aside class="property-sidebar">
        <div class="sidebar-heading">属性</div>
        <div class="property-scroll">
          <section class="property-section">
            <h3>图像显示</h3>
            <label>
              <span>亮度</span>
              <input v-model.number="brightness" type="range" min="0.3" max="2.5" step="0.1" @input="scheduleRenderAll">
            </label>
            <label>
              <span>对比度</span>
              <input v-model.number="contrast" type="range" min="0.3" max="2.5" step="0.1" @input="scheduleRenderAll">
            </label>
            <label>
              <span>画笔大小</span>
              <input v-model.number="brushSize" type="range" min="1" max="40" step="1">
            </label>
          </section>

          <section v-if="selectedMask" class="property-section">
            <h3>选中掩膜</h3>
            <div class="property-value-row"><span>名称</span><strong>{{ selectedMask.name }}</strong></div>
            <div class="property-value-row"><span>体积</span><strong>{{ selectedMask.volume.toFixed(2) }} mL</strong></div>
            <label>
              <span>颜色</span>
              <input v-model="selectedMask.color" type="color" @input="markDirtyAndRender">
            </label>
            <label>
              <span>透明度</span>
              <input
                :value="Math.round(selectedMask.opacity * 100)"
                type="range"
                min="0"
                max="100"
                @input="selectedMask.opacity = Number($event.target.value) / 100; markDirtyAndRender()"
              >
            </label>
            <button class="remove-mask-button" type="button" @click="removeMask(selectedMask)">移除这个掩膜</button>
          </section>
          <div v-else class="empty-copy compact">选择一个掩膜后可编辑。</div>

          <section class="property-section">
            <h3>快捷键</h3>
            <div class="shortcut-grid">
              <kbd>V</kbd><span>浏览 / 定位</span>
              <kbd>B</kbd><span>画笔</span>
              <kbd>E</kbd><span>橡皮擦</span>
              <kbd>T</kbd><span>选择并平移</span>
              <kbd>G</kbd><span>显示 / 隐藏网格</span>
              <kbd>← →</kbd><span>轴位切片</span>
              <kbd>↑ ↓</kbd><span>冠状位切片</span>
              <kbd>[ ]</kbd><span>矢状位切片</span>
              <kbd>Ctrl+Z</kbd><span>撤销</span>
              <kbd>Ctrl+S</kbd><span>保存修改</span>
              <kbd>Esc</kbd><span>浏览模式</span>
            </div>
          </section>
        </div>
      </aside>
    </section>

    <footer class="editor-statusbar">
      <span :class="{ ok: statusOk }">{{ statusText }}</span>
      <span>X: {{ cursor.x }} · Y: {{ cursor.y }} · Z: {{ cursor.z }}</span>
    </footer>

    <div v-if="loading" class="editor-loader">
      <span class="loader-spinner"></span>
      <strong>{{ loadingText }}</strong>
    </div>
  </main>
</template>

<script setup>
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue';
import JSZip from 'jszip';
import pako from 'pako';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const palette = ['#36a9e1', '#f3c74f', '#36c98f', '#ef7fa0', '#a78bfa', '#fb923c', '#22d3ee', '#e879f9'];
const tools = [
  { mode: 'browse', label: '浏览', requiresMask: false },
  { mode: 'brush', label: '画笔', requiresMask: true },
  { mode: 'eraser', label: '橡皮擦', requiresMask: true },
  { mode: 'translate', label: '选择/平移', requiresMask: true },
];
const planeList = [
  { key: 'axial', label: '轴位 Axial', orientation: 'R · A' },
  { key: 'coronal', label: '冠状位 Coronal', orientation: 'R · S' },
  { key: 'sagittal', label: '矢状位 Sagittal', orientation: 'A · S' },
];

const images = shallowRef([]);
const activeImageId = ref('');
const image = computed(() => images.value.find(item => item.id === activeImageId.value) || null);
const masks = ref([]);
const collapsedImageIds = reactive(new Set());
const fullscreenPlane = ref('');
const selectedMaskId = ref('');
const selectedMask = computed(() => {
  const mask = masks.value.find(item => item.id === selectedMaskId.value);
  return mask?.imageId === activeImageId.value ? mask : null;
});
const visibleMasksForActiveImage = computed(() => masks.value.filter(mask => mask.imageId === activeImageId.value && mask.visible));
const cursor = reactive({ x: 0, y: 0, z: 0 });
const zooms = reactive({ axial: 1, coronal: 1, sagittal: 1 });
const brightness = ref(1);
const contrast = ref(1);
const brushSize = ref(1);
const mode = ref('browse');
const showGrid = ref(true);
const dirty = ref(false);
const undoStack = ref([]);
const loading = ref(false);
const loadingText = ref('');
const statusText = ref('等待导入图像');
const statusOk = ref(false);
const dragOver = ref(false);
const drawing = ref(false);
const activePlane = ref('');
const translateDrag = ref(null);
const threeContainer = ref(null);
const canvases = {};
let renderFrame = 0;
let threeRenderer = null;
let threeScene = null;
let threeCamera = null;
let threeControls = null;
let threeMaskGroup = null;
let threeAnimationFrame = 0;
let threeResizeObserver = null;
let threeRefreshFrame = 0;
let threeRefreshTimer = 0;
let threeRefreshIdle = 0;

function setCanvasRef(key, element) {
  if (element) canvases[key] = element;
}

function setStatus(message, ok = false) {
  statusText.value = message;
  statusOk.value = ok;
}

function setLoading(value, text = '') {
  loading.value = value;
  loadingText.value = text;
}

function masksForImage(imageId) {
  return masks.value.filter(mask => mask.imageId === imageId);
}

function toggleImageGroup(imageId) {
  if (collapsedImageIds.has(imageId)) collapsedImageIds.delete(imageId);
  else collapsedImageIds.add(imageId);
}

function togglePlaneFullscreen(plane) {
  fullscreenPlane.value = fullscreenPlane.value === plane ? '' : plane;
  nextTick(() => {
    scheduleRenderAll();
    resize3DRenderer();
  });
}

function setup3DRenderer() {
  if (!threeContainer.value || threeRenderer) return;
  threeScene = new THREE.Scene();
  threeScene.background = new THREE.Color(0x060a12);
  threeCamera = new THREE.PerspectiveCamera(38, 1, 0.1, 4000);
  threeCamera.position.set(120, 100, 150);

  threeRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  threeRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  threeRenderer.outputColorSpace = THREE.SRGBColorSpace;
  threeContainer.value.prepend(threeRenderer.domElement);

  threeControls = new OrbitControls(threeCamera, threeRenderer.domElement);
  threeControls.enableDamping = true;
  threeControls.dampingFactor = 0.08;
  threeControls.target.set(0, 0, 0);

  threeScene.add(new THREE.HemisphereLight(0xffffff, 0x263550, 2.3));
  const keyLight = new THREE.DirectionalLight(0xffffff, 2.5);
  keyLight.position.set(2, 3, 4);
  threeScene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0x7dd3fc, 1.4);
  fillLight.position.set(-3, -1, 2);
  threeScene.add(fillLight);

  threeMaskGroup = new THREE.Group();
  threeScene.add(threeMaskGroup);
  resize3DRenderer();
  animate3D();
}

function animate3D() {
  if (!threeRenderer || !threeScene || !threeCamera) return;
  threeAnimationFrame = requestAnimationFrame(animate3D);
  threeControls?.update();
  threeRenderer.render(threeScene, threeCamera);
}

function resize3DRenderer() {
  if (!threeRenderer || !threeContainer.value || !threeCamera) return;
  const width = Math.max(1, threeContainer.value.clientWidth);
  const height = Math.max(1, threeContainer.value.clientHeight);
  threeRenderer.setSize(width, height, false);
  threeCamera.aspect = width / height;
  threeCamera.updateProjectionMatrix();
}

function refresh3DScene() {
  if (!threeRenderer || !threeMaskGroup || !image.value) return;
  disposeThreeGroup(threeMaskGroup);
  const source = image.value;
  const [, nx, ny, nz] = source.dim;
  const [sx, sy, sz] = source.pixdim;

  for (const mask of visibleMasksForActiveImage.value) {
    const surfaceVoxels = collectSurfaceVoxels(mask, nx, ny, nz);
    if (!surfaceVoxels.length) continue;
    const stride = Math.max(1, Math.ceil(surfaceVoxels.length / 14000));
    const count = Math.ceil(surfaceVoxels.length / stride);
    const material = new THREE.MeshStandardMaterial({
      color: mask.color,
      transparent: true,
      opacity: Math.max(0.18, mask.opacity),
      roughness: 0.62,
      metalness: 0.03,
    });
    const geometry = new THREE.BoxGeometry(sx, sy, sz);
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    const matrix = new THREE.Matrix4();
    let instanceIndex = 0;
    for (let index = 0; index < count; index++) {
      const sampleIndex = stride === 1
        ? index
        : Math.floor(((index * 0.61803398875) % 1) * surfaceVoxels.length);
      const voxelIndex = surfaceVoxels[sampleIndex];
      const z = Math.floor(voxelIndex / (nx * ny));
      const remainder = voxelIndex - z * nx * ny;
      const y = Math.floor(remainder / nx);
      const x = remainder - y * nx;
      matrix.makeTranslation(
        (x - nx / 2) * sx,
        (z - nz / 2) * sz,
        (y - ny / 2) * sy,
      );
      mesh.setMatrixAt(instanceIndex++, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    threeMaskGroup.add(mesh);
  }
  frame3DScene();
}

function schedule3DRefresh() {
  if (threeRefreshFrame) cancelAnimationFrame(threeRefreshFrame);
  if (threeRefreshTimer) clearTimeout(threeRefreshTimer);
  if (threeRefreshIdle && window.cancelIdleCallback) window.cancelIdleCallback(threeRefreshIdle);
  threeRefreshFrame = 0;
  threeRefreshIdle = 0;
  threeRefreshTimer = window.setTimeout(() => {
    threeRefreshTimer = 0;
    const refresh = () => {
      threeRefreshIdle = 0;
      refresh3DScene();
    };
    if (window.requestIdleCallback) {
      threeRefreshIdle = window.requestIdleCallback(refresh, { timeout: 500 });
    } else {
      threeRefreshFrame = requestAnimationFrame(() => {
        threeRefreshFrame = 0;
        refresh();
      });
    }
  }, 120);
}

function collectSurfaceVoxels(mask, nx, ny, nz) {
  const result = [];
  const sliceSize = nx * ny;
  const activeIndices = mask.activeIndices || collectActiveIndices(mask.data);
  for (let cursor = 0; cursor < activeIndices.length; cursor++) {
    const index = activeIndices[cursor];
    const z = Math.floor(index / sliceSize);
    const remainder = index - z * sliceSize;
    const y = Math.floor(remainder / nx);
    const x = remainder - y * nx;
    const surface = x === 0 || x === nx - 1 || y === 0 || y === ny - 1 || z === 0 || z === nz - 1
      || mask.data[index - 1] <= 0 || mask.data[index + 1] <= 0
      || mask.data[index - nx] <= 0 || mask.data[index + nx] <= 0
      || mask.data[index - sliceSize] <= 0 || mask.data[index + sliceSize] <= 0;
    if (surface) result.push(index);
  }
  return result;
}

function frame3DScene() {
  if (!threeCamera || !threeControls || !image.value) return;
  const [, nx, ny, nz] = image.value.dim;
  const [sx, sy, sz] = image.value.pixdim;
  const radius = Math.max(nx * sx, ny * sy, nz * sz) * 0.72;
  threeCamera.position.set(radius, radius * 0.72, radius * 1.15);
  threeControls.target.set(0, 0, 0);
  threeControls.update();
}

function reset3DView() {
  frame3DScene();
}

function disposeThreeGroup(group) {
  while (group.children.length) {
    const child = group.children.pop();
    child.geometry?.dispose();
    if (Array.isArray(child.material)) child.material.forEach(material => material.dispose());
    else child.material?.dispose();
  }
}

function destroy3DRenderer() {
  if (threeAnimationFrame) cancelAnimationFrame(threeAnimationFrame);
  if (threeRefreshFrame) cancelAnimationFrame(threeRefreshFrame);
  if (threeRefreshTimer) clearTimeout(threeRefreshTimer);
  if (threeRefreshIdle && window.cancelIdleCallback) window.cancelIdleCallback(threeRefreshIdle);
  threeResizeObserver?.disconnect();
  threeControls?.dispose();
  if (threeMaskGroup) disposeThreeGroup(threeMaskGroup);
  threeRenderer?.dispose();
  threeRenderer?.domElement.remove();
  threeRenderer = null;
  threeScene = null;
  threeCamera = null;
  threeControls = null;
  threeMaskGroup = null;
}

function stripExtension(name) {
  return String(name || '').replace(/\.nii\.gz$/i, '').replace(/\.nii$/i, '');
}

async function parseFile(file) {
  let bytes = new Uint8Array(await file.arrayBuffer());
  if (file.name.toLowerCase().endsWith('.gz')) bytes = pako.inflate(bytes);
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  return parseNifti(buffer);
}

async function parseNifti(buffer) {
  const view = new DataView(buffer);
  let littleEndian = true;
  let headerSize = view.getInt32(0, littleEndian);
  if (headerSize !== 348) {
    littleEndian = false;
    headerSize = view.getInt32(0, littleEndian);
  }
  if (headerSize !== 348) throw new Error('仅支持 NIfTI-1 文件');

  const dim = Array.from({ length: 8 }, (_, index) => view.getInt16(40 + index * 2, littleEndian));
  const qfac = view.getFloat32(76, littleEndian) < 0 ? -1 : 1;
  const pixdim = Array.from({ length: 3 }, (_, index) => Math.abs(view.getFloat32(80 + index * 4, littleEndian)) || 1);
  const intentCode = view.getInt16(68, littleEndian);
  const datatype = view.getInt16(70, littleEndian);
  const bitsPerPixel = view.getInt16(72, littleEndian);
  const voxelOffset = Math.floor(view.getFloat32(108, littleEndian));
  let slope = view.getFloat32(112, littleEndian);
  const intercept = view.getFloat32(116, littleEndian);
  const qformCode = view.getInt16(252, littleEndian);
  const sformCode = view.getInt16(254, littleEndian);
  const description = readAscii(view, 148, 80);
  const auxiliaryFile = readAscii(view, 228, 24);
  const intentName = readAscii(view, 328, 16);
  const sform = sformCode > 0
    ? Array.from({ length: 12 }, (_, index) => view.getFloat32(280 + index * 4, littleEndian))
    : null;
  const qform = qformCode > 0
    ? createQformMatrix(view, littleEndian, pixdim, qfac)
    : null;
  if (!slope) slope = 1;

  const [, nx, ny, nz] = dim;
  const voxelCount = nx * ny * nz;
  const bytesPerVoxel = bitsPerPixel / 8;
  if (!Number.isFinite(voxelCount) || voxelCount <= 0 || voxelOffset + voxelCount * bytesPerVoxel > buffer.byteLength) {
    throw new Error('NIfTI 数据长度无效');
  }

  const readValue = offset => {
    switch (datatype) {
      case 2: return view.getUint8(offset);
      case 4: return view.getInt16(offset, littleEndian);
      case 8: return view.getInt32(offset, littleEndian);
      case 16: return view.getFloat32(offset, littleEndian);
      case 64: return view.getFloat64(offset, littleEndian);
      case 256: return view.getInt8(offset);
      case 512: return view.getUint16(offset, littleEndian);
      case 768: return view.getUint32(offset, littleEndian);
      default: throw new Error(`暂不支持 NIfTI datatype ${datatype}`);
    }
  };

  const data = new Float32Array(voxelCount);
  for (let index = 0; index < voxelCount; index++) {
    data[index] = readValue(voxelOffset + index * bytesPerVoxel) * slope + intercept;
    if (index > 0 && index % Math.max(1, Math.floor(voxelCount / 8)) === 0) await new Promise(resolve => setTimeout(resolve, 0));
  }
  const contentStats = analyzeVoxelContent(data);

  return {
    dim,
    pixdim,
    data,
    headerBytes: new Uint8Array(buffer.slice(0, Math.max(352, voxelOffset))),
    littleEndian,
    datatype,
    datatypeLabel: niftiDatatypeLabel(datatype),
    intentCode,
    qformCode,
    sformCode,
    sform,
    qform,
    description,
    auxiliaryFile,
    intentName,
    contentStats,
    geometryKey: createGeometryKey(dim, pixdim, sform || qform),
  };
}

function createQformMatrix(view, littleEndian, pixdim, qfac) {
  const b = view.getFloat32(256, littleEndian);
  const c = view.getFloat32(260, littleEndian);
  const d = view.getFloat32(264, littleEndian);
  const a = Math.sqrt(Math.max(0, 1 - b * b - c * c - d * d));
  const x = view.getFloat32(268, littleEndian);
  const y = view.getFloat32(272, littleEndian);
  const z = view.getFloat32(276, littleEndian);
  const [dx, dy, dzBase] = pixdim;
  const dz = dzBase * qfac;
  return [
    (a * a + b * b - c * c - d * d) * dx, 2 * (b * c - a * d) * dy, 2 * (b * d + a * c) * dz, x,
    2 * (b * c + a * d) * dx, (a * a + c * c - b * b - d * d) * dy, 2 * (c * d - a * b) * dz, y,
    2 * (b * d - a * c) * dx, 2 * (c * d + a * b) * dy, (a * a + d * d - c * c - b * b) * dz, z,
  ];
}

function readAscii(view, offset, length) {
  let value = '';
  for (let index = 0; index < length; index++) {
    const code = view.getUint8(offset + index);
    if (!code) break;
    if (code >= 32 && code <= 126) value += String.fromCharCode(code);
  }
  return value.trim();
}

function analyzeVoxelContent(data) {
  const sampleLimit = 100000;
  const stride = Math.max(1, Math.floor(data.length / sampleLimit));
  const unique = new Set();
  let sampled = 0;
  let integerCount = 0;
  let nonZero = 0;
  let min = Infinity;
  let max = -Infinity;
  for (let index = 0; index < data.length; index += stride) {
    const value = data[index];
    if (!Number.isFinite(value)) continue;
    sampled++;
    if (value !== 0) nonZero++;
    if (Math.abs(value - Math.round(value)) < 1e-6) integerCount++;
    min = Math.min(min, value);
    max = Math.max(max, value);
    if (unique.size <= 512) unique.add(value);
  }
  const uniqueCount = unique.size;
  const integerRatio = sampled ? integerCount / sampled : 0;
  const nonZeroRatio = sampled ? nonZero / sampled : 0;
  const labelLike = uniqueCount <= 32 && integerRatio > 0.995 && nonZeroRatio < 0.75;
  return { uniqueCount, integerRatio, nonZeroRatio, min, max, labelLike };
}

function createGeometryKey(dim, pixdim, sform) {
  const dims = [dim[1], dim[2], dim[3]].join('x');
  const spacing = pixdim.map(value => Number(value).toFixed(5)).join(',');
  const matrix = sform ? sform.map(value => Number(value).toFixed(4)).join(',') : 'no-sform';
  return `${dims}|${spacing}|${matrix}`;
}

async function handleDataInput(event) {
  const files = [...(event.target.files || [])];
  event.target.value = '';
  if (files.length) await importSceneFiles(files);
}

async function importSceneFiles(inputFiles) {
  setLoading(true, '正在遍历并解析场景数据...');
  await nextTick();
  const errors = [];
  try {
    const files = await expandInputFiles(inputFiles);
    const niftiFiles = files.filter(file => /\.nii(\.gz)?$/i.test(file.name));
    const entries = [];
    for (let index = 0; index < niftiFiles.length; index++) {
      try {
        const file = niftiFiles[index];
        const parsed = await parseFile(file);
        entries.push({
          file,
          parsed,
          sourceIndex: index,
          role: classifyRole(file.name, parsed),
        });
      } catch (error) {
        errors.push(`${niftiFiles[index].name}: ${error.message}`);
      }
    }
    const volumeEntries = entries.filter(entry => entry.role === 'image');
    const maskEntries = entries.filter(entry => entry.role === 'mask');

    for (const entry of volumeEntries) {
      try {
        addImageVolume(entry);
      } catch (error) {
        errors.push(`${entry.file.name}: ${error.message}`);
      }
    }
    for (const entry of maskEntries) {
      try {
        addMaskVolume(entry);
      } catch (error) {
        errors.push(`${entry.file.name}: ${error.message}`);
      }
    }

    if (!activeImageId.value && images.value.length) activateImage(images.value[0].id);
    setStatus(`已导入 ${volumeEntries.length} 个图像、${maskEntries.length} 个掩膜`, true);
    if (errors.length) window.alert(`部分文件未导入：\n${errors.join('\n')}`);
    await nextTick();
    renderAll();
    schedule3DRefresh();
  } finally {
    setLoading(false);
  }
}

async function expandInputFiles(files) {
  const expanded = [];
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith('.zip')) {
      expanded.push(file);
      continue;
    }
    const zip = await JSZip.loadAsync(file);
    for (const [path, entry] of Object.entries(zip.files)) {
      if (entry.dir || path.startsWith('__MACOSX/') || !/\.nii(\.gz)?$/i.test(path)) continue;
      const bytes = await entry.async('uint8array');
      const name = path.split(/[\\/]/).pop();
      expanded.push(new File([bytes], name, { type: 'application/octet-stream' }));
    }
  }
  return expanded;
}

function addImageVolume(entry) {
  const { file, parsed, sourceIndex } = entry;
  const windowRange = calculateWindowRange(parsed.data);
  const volume = markRaw({
    ...parsed,
    id: `image_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    data: markRaw(parsed.data),
    headerBytes: markRaw(parsed.headerBytes),
    name: file.name,
    sourceIndex,
    sceneKey: inferSceneKey(file.name),
    modalityHint: inferModality(file.name, parsed),
    windowMin: windowRange.min,
    windowMax: windowRange.max,
  });
  images.value = [...images.value, volume];
  if (!activeImageId.value) activateImage(volume.id);
}

function addMaskVolume(entry) {
  const { file, parsed, sourceIndex } = entry;
  const owner = findMaskOwner(file.name, parsed, sourceIndex);
  if (!owner) throw new Error('找不到名称前缀和尺寸匹配的图像');
  const data = new Float32Array(parsed.data.length);
  for (let index = 0; index < parsed.data.length; index++) data[index] = parsed.data[index] > 0 ? 1 : 0;
  const voxelCount = countMaskVoxels(data);
  const activeIndices = collectActiveIndices(data);
  const mask = {
    id: `mask_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    imageId: owner.id,
    name: stripExtension(file.name),
    sourceIndex,
    dim: parsed.dim,
    data: markRaw(data),
    headerBytes: markRaw(parsed.headerBytes),
    littleEndian: parsed.littleEndian,
    visible: true,
    color: palette[masks.value.length % palette.length],
    opacity: 0.6,
    sourceDatatype: parsed.datatypeLabel,
    voxelCount,
    activeIndices: markRaw(activeIndices),
    volume: voxelCount * owner.pixdim[0] * owner.pixdim[1] * owner.pixdim[2] / 1000,
  };
  masks.value.push(mask);
  if (owner.id === activeImageId.value) selectedMaskId.value = mask.id;
  dirty.value = true;
}

function handleDrop(event) {
  dragOver.value = false;
  const files = [...event.dataTransfer.files].filter(file => /\.(nii|nii\.gz|zip)$/i.test(file.name));
  if (files.length) importSceneFiles(files);
}

function activateImage(imageId) {
  const volume = images.value.find(item => item.id === imageId);
  if (!volume) return;
  activeImageId.value = imageId;
  cursor.x = Math.floor(volume.dim[1] / 2);
  cursor.y = Math.floor(volume.dim[2] / 2);
  cursor.z = Math.floor(volume.dim[3] / 2);
  selectedMaskId.value = masks.value.find(mask => mask.imageId === imageId)?.id || '';
  Object.assign(zooms, { axial: 1, coronal: 1, sagittal: 1 });
  scheduleRenderAll();
  schedule3DRefresh();
}

function selectMask(mask) {
  if (mask.imageId !== activeImageId.value) activateImage(mask.imageId);
  selectedMaskId.value = mask.id;
}

function imageName(imageId) {
  return stripExtension(images.value.find(item => item.id === imageId)?.name || '未关联');
}

function removeImage(volume) {
  const relatedMasks = masks.value.filter(mask => mask.imageId === volume.id);
  const message = relatedMasks.length
    ? `移除图像会同时清空关联的 ${relatedMasks.length} 个掩膜，确定继续吗？`
    : `确定移除图像“${stripExtension(volume.name)}”吗？`;
  if (!window.confirm(message)) return;
  images.value = images.value.filter(item => item.id !== volume.id);
  masks.value = masks.value.filter(mask => mask.imageId !== volume.id);
  selectedMaskId.value = '';
  undoStack.value = [];
  dirty.value = false;
  drawing.value = false;
  translateDrag.value = null;
  mode.value = 'browse';
  const nextImage = images.value[0];
  activeImageId.value = '';
  if (nextImage) activateImage(nextImage.id);
  else {
    cursor.x = 0; cursor.y = 0; cursor.z = 0;
    for (const canvas of Object.values(canvases)) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  }
  setStatus(`图像 ${stripExtension(volume.name)} 已移除`);
  schedule3DRefresh();
}

function planeMax(plane) {
  if (!image.value) return 0;
  if (plane === 'axial') return image.value.dim[3] - 1;
  if (plane === 'coronal') return image.value.dim[2] - 1;
  return image.value.dim[1] - 1;
}

function planeSlice(plane) {
  if (plane === 'axial') return cursor.z;
  if (plane === 'coronal') return cursor.y;
  return cursor.x;
}

function setPlaneSlice(plane, value) {
  if (plane === 'axial') cursor.z = value;
  else if (plane === 'coronal') cursor.y = value;
  else cursor.x = value;
  scheduleRenderAll();
}

function handlePlaneWheel(event, plane) {
  const step = event.deltaY > 0 ? 1 : -1;
  setPlaneSlice(plane, Math.max(0, Math.min(planeMax(plane), planeSlice(plane) + step)));
}

function zoomPlane(plane, delta) {
  zooms[plane] = Math.max(0.5, Math.min(6, zooms[plane] + delta));
  scheduleRenderPlane(plane);
}

function resetPlaneZoom(plane) {
  zooms[plane] = 1;
  scheduleRenderPlane(plane);
}

function renderAll() {
  if (renderFrame) {
    cancelAnimationFrame(renderFrame);
    renderFrame = 0;
  }
  if (!image.value) return;
  for (const plane of planeList) renderPlane(plane.key);
}

function scheduleRenderAll() {
  if (renderFrame) return;
  renderFrame = requestAnimationFrame(() => {
    renderFrame = 0;
    if (!image.value) return;
    for (const plane of planeList) renderPlane(plane.key);
  });
}

function scheduleRenderPlane(plane) {
  if (renderFrame) cancelAnimationFrame(renderFrame);
  renderFrame = requestAnimationFrame(() => {
    renderFrame = 0;
    renderPlane(plane);
  });
}

function renderPlane(plane) {
  const source = image.value;
  const canvas = canvases[plane];
  if (!source || !canvas) return;
  const context = canvas.getContext('2d');
  const [, nx, ny, nz] = source.dim;
  let width;
  let height;
  let toVoxel;
  if (plane === 'axial') {
    width = nx; height = ny;
    toVoxel = (u, v) => ({ x: u, y: v, z: cursor.z });
  } else if (plane === 'coronal') {
    width = nx; height = nz;
    toVoxel = (u, v) => ({ x: u, y: cursor.y, z: nz - 1 - v });
  } else {
    width = ny; height = nz;
    toVoxel = (u, v) => ({ x: cursor.x, y: u, z: nz - 1 - v });
  }
  canvas.width = width;
  canvas.height = height;

  const frame = context.createImageData(width, height);
  const previewDelta = translateDrag.value?.delta || null;
  const visibleMasks = masks.value
    .filter(mask => mask.visible && mask.imageId === activeImageId.value)
    .map(mask => ({
      id: mask.id,
      data: mask.data,
      opacity: mask.opacity,
      rgb: hexToRgb(mask.color),
      delta: mask.id === selectedMaskId.value ? previewDelta : null,
    }));
  const min = source.windowMin;
  const max = source.windowMax;
  for (let v = 0; v < height; v++) {
    for (let u = 0; u < width; u++) {
      const voxel = toVoxel(u, v);
      const voxelIndex = voxel.z * nx * ny + voxel.y * nx + voxel.x;
      let intensity = (source.data[voxelIndex] - min) / (max - min) * 255 * brightness.value;
      intensity = ((intensity / 255 - 0.5) * contrast.value + 0.5) * 255;
      intensity = Math.max(0, Math.min(255, intensity));
      let red = intensity;
      let green = intensity;
      let blue = intensity;
      for (const mask of visibleMasks) {
        let maskIndex = voxelIndex;
        if (mask.delta) {
          const sourceX = voxel.x - mask.delta.dx;
          const sourceY = voxel.y - mask.delta.dy;
          const sourceZ = voxel.z - mask.delta.dz;
          if (sourceX < 0 || sourceX >= nx || sourceY < 0 || sourceY >= ny || sourceZ < 0 || sourceZ >= nz) continue;
          maskIndex = sourceZ * nx * ny + sourceY * nx + sourceX;
        }
        if (mask.data[maskIndex] <= 0) continue;
        const color = mask.rgb;
        red = red * (1 - mask.opacity) + color.r * mask.opacity;
        green = green * (1 - mask.opacity) + color.g * mask.opacity;
        blue = blue * (1 - mask.opacity) + color.b * mask.opacity;
      }
      const pixelIndex = (v * width + u) * 4;
      frame.data[pixelIndex] = red;
      frame.data[pixelIndex + 1] = green;
      frame.data[pixelIndex + 2] = blue;
      frame.data[pixelIndex + 3] = 255;
    }
  }
  context.putImageData(frame, 0, 0);
  if (showGrid.value) drawGrid(plane, context, width, height);
  if (mode.value === 'translate' && selectedMask.value) {
    drawSelectionBox(plane, context, width, height, toVoxel, selectedMask.value, previewDelta);
  }
  fitCanvas(plane, canvas, width, height);
}

function drawSelectionBox(plane, context, width, height, toVoxel, mask, delta = null) {
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  const [, nx, ny, nz] = image.value.dim;
  for (let v = 0; v < height; v++) {
    for (let u = 0; u < width; u++) {
      const voxel = toVoxel(u, v);
      const sourceX = voxel.x - (delta?.dx || 0);
      const sourceY = voxel.y - (delta?.dy || 0);
      const sourceZ = voxel.z - (delta?.dz || 0);
      if (sourceX < 0 || sourceX >= nx || sourceY < 0 || sourceY >= ny || sourceZ < 0 || sourceZ >= nz) continue;
      const voxelIndex = sourceZ * nx * ny + sourceY * nx + sourceX;
      if (mask.data[voxelIndex] <= 0) continue;
      minX = Math.min(minX, u);
      minY = Math.min(minY, v);
      maxX = Math.max(maxX, u);
      maxY = Math.max(maxY, v);
    }
  }
  if (maxX < minX || maxY < minY) return;
  const padding = 3;
  minX = Math.max(0, minX - padding);
  minY = Math.max(0, minY - padding);
  maxX = Math.min(width - 1, maxX + padding);
  maxY = Math.min(height - 1, maxY + padding);
  context.save();
  context.strokeStyle = '#facc15';
  context.fillStyle = '#facc15';
  context.lineWidth = 1.5;
  context.setLineDash([]);
  context.strokeRect(minX + 0.5, minY + 0.5, maxX - minX, maxY - minY);
  const handles = [
    [minX, minY],
    [maxX, minY],
    [minX, maxY],
    [maxX, maxY],
  ];
  for (const [x, y] of handles) context.fillRect(x - 2, y - 2, 5, 5);
  context.fillStyle = 'rgba(250,204,21,.92)';
  context.font = '10px "Segoe UI"';
  context.fillText(mask.name, minX + 4, Math.max(11, minY - 5));
  context.restore();
}

function drawGrid(plane, context, width, height) {
  let x;
  let y;
  if (plane === 'axial') { x = cursor.x; y = cursor.y; }
  else if (plane === 'coronal') { x = cursor.x; y = height - 1 - cursor.z; }
  else { x = cursor.y; y = height - 1 - cursor.z; }
  context.save();
  context.strokeStyle = 'rgba(255,255,255,.65)';
  context.lineWidth = 1;
  context.setLineDash([3, 3]);
  context.beginPath();
  context.moveTo(x + 0.5, 0);
  context.lineTo(x + 0.5, height);
  context.moveTo(0, y + 0.5);
  context.lineTo(width, y + 0.5);
  context.stroke();
  context.restore();
}

function fitCanvas(plane, canvas, width, height) {
  const container = canvas.parentElement;
  const [sx, sy, sz] = image.value.pixdim;
  let physicalWidth = width;
  let physicalHeight = height;
  if (plane === 'axial') { physicalWidth *= sx; physicalHeight *= sy; }
  else if (plane === 'coronal') { physicalWidth *= sx; physicalHeight *= sz; }
  else { physicalWidth *= sy; physicalHeight *= sz; }
  const imageAspect = physicalWidth / physicalHeight;
  const containerAspect = Math.max(1, container.clientWidth) / Math.max(1, container.clientHeight);
  let cssWidth;
  let cssHeight;
  if (imageAspect >= containerAspect) {
    cssWidth = container.clientWidth;
    cssHeight = cssWidth / imageAspect;
  } else {
    cssHeight = container.clientHeight;
    cssWidth = cssHeight * imageAspect;
  }
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  canvas.style.transform = `scale(${zooms[plane]})`;
}

function canvasPoint(event, plane) {
  const canvas = canvases[plane];
  const rect = canvas.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(canvas.width - 1, Math.floor((event.clientX - rect.left) / rect.width * canvas.width))),
    y: Math.max(0, Math.min(canvas.height - 1, Math.floor((event.clientY - rect.top) / rect.height * canvas.height))),
  };
}

function pointToVoxel(plane, point) {
  const [, , , nz] = image.value.dim;
  if (plane === 'axial') return { x: point.x, y: point.y, z: cursor.z };
  if (plane === 'coronal') return { x: point.x, y: cursor.y, z: nz - 1 - point.y };
  return { x: cursor.x, y: point.x, z: nz - 1 - point.y };
}

function locateFromCanvas(event, plane) {
  if (!image.value) return;
  const voxel = pointToVoxel(plane, canvasPoint(event, plane));
  Object.assign(cursor, voxel);
  scheduleRenderAll();
}

function handleCanvasDown(event, plane) {
  if (!image.value) return;
  activePlane.value = plane;
  if (mode.value === 'browse') {
    locateFromCanvas(event, plane);
    return;
  }
  if (!selectedMask.value) return;
  if (mode.value === 'translate') {
    saveUndo(true);
    const start = canvasPoint(event, plane);
    translateDrag.value = {
      plane,
      start,
      current: start,
      delta: { dx: 0, dy: 0, dz: 0 },
    };
    return;
  }
  saveUndo();
  drawing.value = true;
  paintAt(event, plane);
}

function handleCanvasMove(event, plane) {
  if (translateDrag.value && translateDrag.value.plane === plane) {
    const current = canvasPoint(event, plane);
    translateDrag.value.current = current;
    translateDrag.value.delta = translationDelta(
      plane,
      current.x - translateDrag.value.start.x,
      current.y - translateDrag.value.start.y,
    );
    scheduleRenderAll();
    return;
  }
  if (!drawing.value || activePlane.value !== plane) return;
  paintAt(event, plane);
}

function paintAt(event, plane) {
  const mask = selectedMask.value;
  if (!mask || !['brush', 'eraser'].includes(mode.value)) return;
  const center = pointToVoxel(plane, canvasPoint(event, plane));
  const [, nx, ny, nz] = image.value.dim;
  const radius = brushSize.value;
  for (let dv = -radius; dv <= radius; dv++) {
    for (let du = -radius; du <= radius; du++) {
      if (du * du + dv * dv > radius * radius) continue;
      let { x, y, z } = center;
      if (plane === 'axial') { x += du; y += dv; }
      else if (plane === 'coronal') { x += du; z -= dv; }
      else { y += du; z -= dv; }
      if (x < 0 || x >= nx || y < 0 || y >= ny || z < 0 || z >= nz) continue;
      mask.data[z * nx * ny + y * nx + x] = mode.value === 'brush' ? 1 : 0;
    }
  }
  dirty.value = true;
  scheduleRenderAll();
}

function handlePointerUp(event) {
  if (translateDrag.value) {
    const delta = translateDrag.value.delta;
    translateDrag.value = null;
    translateMask(delta);
  }
  if (drawing.value) {
    drawing.value = false;
    updateMaskVolume(selectedMask.value);
    schedule3DRefresh();
    setStatus('掩膜已修改，尚未保存', true);
  }
}

function translationDelta(plane, deltaU, deltaV) {
  if (plane === 'axial') return { dx: deltaU, dy: deltaV, dz: 0 };
  if (plane === 'coronal') return { dx: deltaU, dy: 0, dz: -deltaV };
  return { dx: 0, dy: deltaU, dz: -deltaV };
}

function translateMask(delta) {
  const mask = selectedMask.value;
  if (!mask || !delta || (!delta.dx && !delta.dy && !delta.dz)) {
    scheduleRenderAll();
    return;
  }
  const [, nx, ny, nz] = image.value.dim;
  const { dx, dy, dz } = delta;
  const sliceSize = nx * ny;
  const shifted = new Float32Array(mask.data.length);
  const sourceIndices = mask.activeIndices || collectActiveIndices(mask.data);
  const translatedIndices = new Int32Array(sourceIndices.length);
  let translatedCount = 0;
  for (let index = 0; index < sourceIndices.length; index++) {
    const sourceIndex = sourceIndices[index];
    const z = Math.floor(sourceIndex / sliceSize);
    const remainder = sourceIndex - z * sliceSize;
    const y = Math.floor(remainder / nx);
    const x = remainder - y * nx;
    const tx = x + dx;
    const ty = y + dy;
    const tz = z + dz;
    if (tx < 0 || tx >= nx || ty < 0 || ty >= ny || tz < 0 || tz >= nz) continue;
    const targetIndex = tz * sliceSize + ty * nx + tx;
    shifted[targetIndex] = 1;
    translatedIndices[translatedCount++] = targetIndex;
  }
  mask.data = markRaw(shifted);
  mask.activeIndices = markRaw(translatedIndices.slice(0, translatedCount));
  updateMaskVolume(mask, false);
  dirty.value = true;
  scheduleRenderAll();
  schedule3DRefresh();
  setStatus(`已平移掩膜：ΔX ${dx} · ΔY ${dy} · ΔZ ${dz}`, true);
}

function saveUndo(sparse = false) {
  const mask = selectedMask.value;
  if (!mask) return;
  undoStack.value.push(sparse
    ? { maskId: mask.id, activeIndices: new Int32Array(mask.activeIndices || collectActiveIndices(mask.data)) }
    : { maskId: mask.id, data: new Float32Array(mask.data) });
  if (undoStack.value.length > 20) undoStack.value.shift();
}

function undo() {
  const snapshot = undoStack.value.pop();
  if (!snapshot) return;
  const mask = masks.value.find(item => item.id === snapshot.maskId);
  if (mask && snapshot.activeIndices) {
    const restored = new Float32Array(mask.data.length);
    for (let index = 0; index < snapshot.activeIndices.length; index++) restored[snapshot.activeIndices[index]] = 1;
    mask.data = markRaw(restored);
    mask.activeIndices = markRaw(new Int32Array(snapshot.activeIndices));
  } else if (mask) {
    mask.data.set(snapshot.data);
  }
  updateMaskVolume(mask, !snapshot.activeIndices);
  dirty.value = true;
  scheduleRenderAll();
  schedule3DRefresh();
  setStatus('已撤销上一步修改', true);
}

function setMode(nextMode) {
  if (nextMode !== 'browse' && !selectedMask.value) return;
  mode.value = nextMode;
  scheduleRenderAll();
}

function toggleMask(mask) {
  mask.visible = !mask.visible;
  scheduleRenderAll();
  schedule3DRefresh();
}

function removeMask(mask) {
  if (!window.confirm(`确定移除掩膜“${mask.name}”吗？`)) return;
  masks.value = masks.value.filter(item => item.id !== mask.id);
  selectedMaskId.value = masks.value[0]?.id || '';
  dirty.value = true;
  undoStack.value = [];
  scheduleRenderAll();
  schedule3DRefresh();
}

function markDirtyAndRender() {
  dirty.value = true;
  scheduleRenderAll();
  schedule3DRefresh();
}

function countMaskVoxels(data) {
  let count = 0;
  for (let index = 0; index < data.length; index++) if (data[index] > 0) count++;
  return count;
}

function collectActiveIndices(data) {
  const indices = new Int32Array(countMaskVoxels(data));
  let cursor = 0;
  for (let index = 0; index < data.length; index++) {
    if (data[index] > 0) indices[cursor++] = index;
  }
  return indices;
}

function updateMaskVolume(mask, rebuildIndices = true) {
  if (!mask) return;
  const owner = images.value.find(item => item.id === mask.imageId);
  if (!owner) return;
  if (rebuildIndices) mask.activeIndices = markRaw(collectActiveIndices(mask.data));
  mask.voxelCount = mask.activeIndices?.length ?? countMaskVoxels(mask.data);
  mask.volume = mask.voxelCount * owner.pixdim[0] * owner.pixdim[1] * owner.pixdim[2] / 1000;
}

function calculateWindowRange(data) {
  let min = Infinity;
  let max = -Infinity;
  for (let index = 0; index < data.length; index++) {
    const value = data[index];
    if (!Number.isFinite(value)) continue;
    min = Math.min(min, value);
    max = Math.max(max, value);
  }
  if (!Number.isFinite(min) || max === min) return { min: 0, max: 1 };
  return { min, max };
}

function buildMaskNifti(mask) {
  const [, nx, ny, nz] = mask.dim;
  const voxelCount = nx * ny * nz;
  const headerSize = Math.max(352, mask.headerBytes.length);
  const buffer = new ArrayBuffer(headerSize + voxelCount);
  const bytes = new Uint8Array(buffer);
  bytes.set(mask.headerBytes.slice(0, headerSize));
  const view = new DataView(buffer);
  view.setInt16(70, 2, mask.littleEndian);
  view.setInt16(72, 8, mask.littleEndian);
  view.setFloat32(108, headerSize, mask.littleEndian);
  view.setFloat32(112, 1, mask.littleEndian);
  view.setFloat32(116, 0, mask.littleEndian);
  for (let index = 0; index < voxelCount; index++) bytes[headerSize + index] = mask.data[index] > 0 ? 1 : 0;
  return buffer;
}

async function buildMasksZip() {
  const zip = new JSZip();
  const used = new Set();
  for (const mask of masks.value) {
    const compressed = await gzipBytes(new Uint8Array(buildMaskNifti(mask)));
    const base = safeName(mask.name);
    let fileName = `${base}.nii.gz`;
    let suffix = 2;
    while (used.has(fileName.toLowerCase())) fileName = `${base}_${suffix++}.nii.gz`;
    used.add(fileName.toLowerCase());
    zip.file(fileName, compressed);
  }
  return zip.generateAsync({ type: 'blob', compression: 'STORE' });
}

async function gzipBytes(bytes) {
  if (typeof CompressionStream !== 'undefined') {
    const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }
  await new Promise(resolve => setTimeout(resolve, 0));
  return pako.gzip(bytes);
}

async function saveChanges() {
  if (!masks.value.length) return;
  setLoading(true, '正在保存修改...');
  await nextTick();
  await new Promise(resolve => requestAnimationFrame(resolve));
  try {
    const blob = await buildMasksZip();
    const suggestedName = `${safeName(stripExtension(image.value.name))}_modified_masks.zip`;
    if ('showSaveFilePicker' in window) {
      const handle = await window.showSaveFilePicker({
        suggestedName,
        types: [{ description: 'ZIP 压缩包', accept: { 'application/zip': ['.zip'] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
    } else {
      downloadBlob(blob, suggestedName);
    }
    dirty.value = false;
    setStatus(`修改已保存，共 ${masks.value.length} 个掩膜`, true);
  } catch (error) {
    if (error.name !== 'AbortError') window.alert(`保存失败：${error.message}`);
  } finally {
    setLoading(false);
  }
}

async function exportSelected() {
  const mask = selectedMask.value;
  if (!mask) return;
  setLoading(true, '正在压缩选中掩膜...');
  await nextTick();
  await new Promise(resolve => requestAnimationFrame(resolve));
  try {
    const compressed = await gzipBytes(new Uint8Array(buildMaskNifti(mask)));
    downloadBlob(new Blob([compressed], { type: 'application/gzip' }), `${safeName(mask.name)}.nii.gz`);
  } finally {
    setLoading(false);
  }
}

async function exportAll() {
  if (!masks.value.length) return;
  setLoading(true, '正在打包掩膜...');
  await nextTick();
  await new Promise(resolve => requestAnimationFrame(resolve));
  try {
    downloadBlob(await buildMasksZip(), 'pds_masks.zip');
  } finally {
    setLoading(false);
  }
}

function downloadBlob(blob, fileName) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function safeName(name) {
  return String(name || 'mask').replace(/[\\/:*?"<>|]/g, '_');
}

function inferModality(fileName, parsed = null) {
  const headerText = [
    parsed?.description,
    parsed?.auxiliaryFile,
    parsed?.intentName,
  ].filter(Boolean).join(' ').toLowerCase();
  const name = `${stripExtension(fileName).toLowerCase()} ${headerText}`;
  if (/(^|[_\-. ])(pet|psma)([_\-. ]|$)/.test(name)) return 'PET / PSMA';
  if (/(^|[_\-. ])ct([_\-. ]|$)/.test(name)) return 'CT';
  if (/(^|[_\-. ])(mri|mr|t2w?|tse|adc|dwi)([_\-. ]|$)/.test(name)) return 'MRI';
  return '未知模态';
}

function classifyRole(fileName, parsed) {
  const metadata = [
    stripExtension(fileName),
    parsed.description,
    parsed.auxiliaryFile,
    parsed.intentName,
  ].filter(Boolean).join(' ').toLowerCase();
  if (/(^|[_\-. ])(mask|seg|label)([_\-. ]|$)|(?:pz|tz|wg)_mask|mask$/.test(metadata)) return 'mask';
  if ([1002, 1003, 1004].includes(parsed.intentCode)) return 'mask';
  return parsed.contentStats.labelLike ? 'mask' : 'image';
}

function inferSceneKey(fileName) {
  const name = stripExtension(fileName).toLowerCase();
  if (name.startsWith('pet') || name.includes('psma')) return 'pet';
  if (name.startsWith('ct')) return 'ct';
  if (name.startsWith('mri') || name.startsWith('mr') || name.includes('t2')) return 'mri';
  return name.replace(/(?:pz|tz|wg|whole)?_?mask.*$/i, '').replace(/[_\-.]+$/g, '');
}

function sameDimensions(left, right) {
  return [1, 2, 3].every(index => left[index] === right[index]);
}

function findMaskOwner(fileName, parsed, sourceIndex) {
  const key = inferSceneKey(fileName);
  const exactName = images.value.find(item => item.sceneKey === key && sameGeometry(item, parsed));
  if (exactName) return exactName;
  const compatible = images.value.filter(item => sameGeometry(item, parsed));
  if (!compatible.length) return null;
  const preceding = compatible
    .filter(item => item.sourceIndex < sourceIndex)
    .sort((left, right) => right.sourceIndex - left.sourceIndex);
  return preceding[0] || compatible[0];
}

function sameGeometry(imageVolume, parsed) {
  if (imageVolume.geometryKey === parsed.geometryKey) return true;
  return sameDimensions(imageVolume.dim, parsed.dim)
    && imageVolume.pixdim.every((value, index) => Math.abs(value - parsed.pixdim[index]) < 1e-4);
}

function niftiDatatypeLabel(datatype) {
  return ({
    2: 'UINT8',
    4: 'INT16',
    8: 'INT32',
    16: 'FLOAT32',
    64: 'FLOAT64',
    256: 'INT8',
    512: 'UINT16',
    768: 'UINT32',
  })[datatype] || `datatype ${datatype}`;
}

function hexToRgb(hex) {
  return {
    r: parseInt(hex.slice(1, 3), 16),
    g: parseInt(hex.slice(3, 5), 16),
    b: parseInt(hex.slice(5, 7), 16),
  };
}

function handleShortcut(event) {
  if (event.repeat) return;
  const key = event.key.toLowerCase();
  if ((event.ctrlKey || event.metaKey) && key === 's') {
    event.preventDefault();
    saveChanges();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === 'z') {
    event.preventDefault();
    undo();
    return;
  }
  if (!image.value) return;
  let handled = true;
  if (event.key === 'Escape' && fullscreenPlane.value) {
    fullscreenPlane.value = '';
    nextTick(() => scheduleRenderAll());
  }
  else if (key === 'v' || event.key === 'Escape') setMode('browse');
  else if (key === 'b') setMode('brush');
  else if (key === 'e') setMode('eraser');
  else if (key === 't') setMode('translate');
  else if (key === 'g') { showGrid.value = !showGrid.value; scheduleRenderAll(); }
  else if (event.key === 'ArrowRight') setPlaneSlice('axial', Math.min(planeMax('axial'), cursor.z + 1));
  else if (event.key === 'ArrowLeft') setPlaneSlice('axial', Math.max(0, cursor.z - 1));
  else if (event.key === 'ArrowUp') setPlaneSlice('coronal', Math.min(planeMax('coronal'), cursor.y + 1));
  else if (event.key === 'ArrowDown') setPlaneSlice('coronal', Math.max(0, cursor.y - 1));
  else if (event.key === ']') setPlaneSlice('sagittal', Math.min(planeMax('sagittal'), cursor.x + 1));
  else if (event.key === '[') setPlaneSlice('sagittal', Math.max(0, cursor.x - 1));
  else handled = false;
  if (handled) event.preventDefault();
}

function handleBeforeUnload(event) {
  if (!dirty.value) return;
  event.preventDefault();
  event.returnValue = '';
}

let resizeObserver;
onMounted(() => {
  window.addEventListener('keydown', handleShortcut, true);
  window.addEventListener('mouseup', handlePointerUp);
  window.addEventListener('beforeunload', handleBeforeUnload);
  setup3DRenderer();
  threeResizeObserver = new ResizeObserver(() => resize3DRenderer());
  if (threeContainer.value) threeResizeObserver.observe(threeContainer.value);
  resizeObserver = new ResizeObserver(() => scheduleRenderAll());
  const grid = document.querySelector('.viewport-grid');
  if (grid) resizeObserver.observe(grid);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleShortcut, true);
  window.removeEventListener('mouseup', handlePointerUp);
  window.removeEventListener('beforeunload', handleBeforeUnload);
  resizeObserver?.disconnect();
  destroy3DRenderer();
  if (renderFrame) cancelAnimationFrame(renderFrame);
});

watch(selectedMaskId, () => scheduleRenderAll());
</script>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

.editor-shell {
  --panel: #101827;
  --panel-soft: #172235;
  --line: rgba(255, 255, 255, 0.09);
  --text: #e7eef9;
  --muted: #8492a8;
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  grid-template-rows: 54px 1fr 28px;
  overflow: hidden;
  color: var(--text);
  background: #080d16;
  font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}

.editor-topbar {
  min-width: 0;
  display: grid;
  grid-template-columns: 235px minmax(0, 1fr) 100px;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  border-bottom: 1px solid var(--line);
  background: #0e1625;
}

.editor-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 14px;
  font-weight: 700;
}

.editor-brand-mark {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #07111d;
  background: #38bdf8;
  font-weight: 900;
}

.editor-toolbar {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  overflow-x: auto;
  scrollbar-width: none;
}

.editor-toolbar::-webkit-scrollbar {
  display: none;
}

.toolbar-button,
.back-link {
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 11px;
  border: 1px solid var(--line);
  border-radius: 5px;
  color: #d7e2f0;
  background: rgba(255, 255, 255, 0.05);
  cursor: pointer;
  font-size: 12px;
  font-weight: 650;
  text-decoration: none;
  white-space: nowrap;
}

.toolbar-button:hover,
.back-link:hover,
.toolbar-button.active {
  border-color: rgba(56, 189, 248, 0.62);
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.14);
}

.toolbar-button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.save-button {
  color: #facc15;
}

.toolbar-divider {
  width: 1px;
  height: 22px;
  flex: 0 0 auto;
  margin: 0 3px;
  background: var(--line);
}

.editor-workspace {
  min-height: 0;
  display: grid;
  grid-template-columns: 250px minmax(420px, 1fr) 270px;
}

.data-sidebar,
.property-sidebar {
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--panel);
}

.data-sidebar {
  border-right: 1px solid var(--line);
}

.property-sidebar {
  border-left: 1px solid var(--line);
}

.sidebar-heading,
.volume-heading {
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid var(--line);
  color: #b9c7da;
  font-size: 11px;
  font-weight: 700;
}

.data-tree,
.property-scroll {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  scrollbar-width: thin;
  scrollbar-color: #35445c transparent;
}

.data-tree::-webkit-scrollbar,
.property-scroll::-webkit-scrollbar {
  width: 7px;
}

.data-tree::-webkit-scrollbar-track,
.property-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.data-tree::-webkit-scrollbar-thumb,
.property-scroll::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 8px;
  background: #35445c;
  background-clip: padding-box;
}

.empty-copy {
  padding: 32px 15px;
  color: var(--muted);
  text-align: center;
  font-size: 12px;
  line-height: 1.7;
}

.empty-copy.compact {
  padding: 18px 8px;
}

.tree-section-title,
.property-section h3 {
  margin: 0;
  padding: 8px 6px;
  color: #68778e;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.7px;
  text-transform: uppercase;
}

.tree-item {
  min-height: 39px;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) 26px 26px;
  align-items: center;
  gap: 5px;
  padding: 5px 6px;
  border: 1px solid transparent;
  border-radius: 5px;
  cursor: pointer;
}

.scene-group {
  margin-bottom: 5px;
}

.tree-item.image-node {
  grid-template-columns: 18px 22px minmax(0, 1fr) 26px;
}

.tree-item.mask-node {
  grid-template-columns: 18px 22px minmax(0, 1fr) 26px 26px;
  margin-left: 8px;
}

.collapse-button {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.collapse-button:hover {
  border-color: #33445c;
  background: #1b293d;
}

.collapse-button span {
  width: 0;
  height: 0;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  border-left: 6px solid #8fa0b7;
  transform: rotate(90deg);
  transition: transform 0.18s ease;
}

.collapse-button.collapsed span {
  transform: rotate(0deg);
}

.tree-indent {
  width: 12px;
  height: 100%;
  border-left: 1px solid #2c3a50;
  border-bottom: 1px solid #2c3a50;
}

.group-masks {
  padding-left: 6px;
}

.tree-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.tree-item.selected {
  border-color: rgba(56, 189, 248, 0.48);
  background: rgba(56, 189, 248, 0.13);
}

.tree-item.incompatible {
  opacity: 0.58;
}

.tree-item.incompatible:hover {
  opacity: 0.86;
}

.node-chip {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 4px;
  color: #08101b;
  font-size: 10px;
  font-weight: 900;
}

.node-chip.image {
  background: #38bdf8;
}

.node-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.node-main strong {
  overflow: hidden;
  color: #dbe7f6;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-main small {
  color: #68778e;
  font-size: 9px;
}

.icon-button {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 4px;
  color: #a4b0c2;
  background: transparent;
  cursor: pointer;
}

.icon-button:hover {
  background: rgba(255, 255, 255, 0.08);
}

.icon-button.remove:hover {
  color: #ff9ca5;
  background: rgba(241, 109, 122, 0.14);
}

.editor-center {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: 38px 1fr;
  background: #02050a;
}

.volume-heading {
  color: #7dd3fc;
  background: #071827;
}

.viewport-grid {
  position: relative;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 1px;
  overflow: hidden;
  background: #263247;
}

.plane-panel.axial {
  grid-column: 1;
  grid-row: 1;
}

.plane-panel.volume-3d {
  grid-column: 2;
  grid-row: 1;
}

.plane-panel.coronal {
  grid-column: 1;
  grid-row: 2;
}

.plane-panel.sagittal {
  grid-column: 2;
  grid-row: 2;
}

.viewport-grid.drop-active::after {
  content: "松开以导入文件";
  position: absolute;
  inset: 14px;
  z-index: 10;
  display: grid;
  place-items: center;
  border: 2px dashed #38bdf8;
  color: #7dd3fc;
  background: rgba(5, 15, 28, 0.9);
  font-size: 17px;
  font-weight: 700;
}

.viewport-grid.has-fullscreen-plane {
  display: block;
}

.plane-panel.fullscreen {
  position: absolute;
  inset: 0;
  z-index: 8;
  width: 100%;
  height: 100%;
}

.plane-panel.concealed {
  display: none;
}

.editor-empty {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: grid;
  place-items: center;
  color: #7d8ca2;
  background: #223047;
  font-size: 13px;
}

.plane-panel {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: 28px 1fr 29px;
  overflow: hidden;
  background: #000;
}

.plane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 7px 0 9px;
  font-size: 10px;
  font-weight: 700;
}

.axial .plane-header {
  color: #ff9696;
  background: #3b151a;
  border-bottom: 1px solid #e25252;
}

.coronal .plane-header {
  color: #86efac;
  background: #11311f;
  border-bottom: 1px solid #38b66c;
}

.sagittal .plane-header {
  color: #fde68a;
  background: #382e10;
  border-bottom: 1px solid #d8aa24;
}

.volume-3d .plane-header {
  color: #c4b5fd;
  background: #20204a;
  border-bottom: 1px solid #8b5cf6;
}

.plane-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.plane-actions button {
  width: 22px;
  height: 21px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  color: inherit;
  background: rgba(0, 0, 0, 0.24);
  cursor: pointer;
}

.plane-actions span {
  min-width: 35px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.canvas-stage {
  position: relative;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.three-stage {
  position: relative;
  min-height: 0;
  overflow: hidden;
  background: radial-gradient(circle at 50% 42%, #19243b, #050810 68%);
}

.three-stage canvas {
  position: absolute;
  inset: 0;
  width: 100% !important;
  height: 100% !important;
}

.three-empty {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-items: center;
  color: #75849a;
  font-size: 11px;
  pointer-events: none;
}

.orientation-cube {
  position: absolute;
  top: 13px;
  right: 14px;
  z-index: 3;
  width: 72px;
  height: 72px;
  border: 1px solid rgba(217, 70, 239, 0.78);
  color: #f5f3ff;
  background: rgba(91, 83, 160, 0.36);
  pointer-events: none;
}

.orientation-cube::before,
.orientation-cube::after {
  position: absolute;
  content: "";
  inset: 10px;
  border: 1px solid rgba(217, 70, 239, 0.72);
}

.orientation-cube span {
  position: absolute;
  font-size: 9px;
  font-weight: 700;
}

.orientation-cube .top { top: 2px; left: 50%; transform: translateX(-50%); }
.orientation-cube .bottom { bottom: 2px; left: 50%; transform: translateX(-50%); }
.orientation-cube .left { left: 3px; top: 50%; transform: translateY(-50%); }
.orientation-cube .right { right: 3px; top: 50%; transform: translateY(-50%); }
.orientation-cube .center { inset: 0; display: grid; place-items: center; }

.three-footer {
  display: flex;
  align-items: center;
  padding: 0 8px;
  color: #78879d;
  background: #0a111c;
  font-size: 9px;
}

.canvas-stage canvas {
  max-width: none;
  max-height: none;
  image-rendering: pixelated;
  transform-origin: center;
}

.orientation-label {
  position: absolute;
  left: 7px;
  bottom: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 9px;
  pointer-events: none;
}

.plane-footer {
  display: grid;
  grid-template-columns: 1fr 50px;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  background: #0a111c;
}

.plane-footer span {
  color: #8fa0b7;
  font-size: 9px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

input[type="range"] {
  height: 14px;
  appearance: none;
  background: transparent;
  cursor: pointer;
}

input[type="range"]::-webkit-slider-runnable-track {
  height: 3px;
  border-radius: 3px;
  background: #334258;
}

input[type="range"]::-webkit-slider-thumb {
  width: 12px;
  height: 12px;
  margin-top: -4.5px;
  appearance: none;
  border: 2px solid #0b1320;
  border-radius: 50%;
  background: #38bdf8;
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.25);
}

input[type="range"]::-moz-range-track {
  height: 3px;
  border-radius: 3px;
  background: #334258;
}

input[type="range"]::-moz-range-thumb {
  width: 10px;
  height: 10px;
  border: 2px solid #0b1320;
  border-radius: 50%;
  background: #38bdf8;
}

.property-section {
  padding: 4px 6px 14px;
  border-bottom: 1px solid var(--line);
}

.property-section label,
.property-value-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  margin: 9px 0;
  color: #91a0b5;
  font-size: 10px;
}

.property-value-row strong {
  overflow: hidden;
  color: #e2eaf5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

input[type="color"] {
  width: 100%;
  height: 27px;
  padding: 2px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: #09111d;
}

.remove-mask-button {
  width: 100%;
  height: 32px;
  border: 1px solid rgba(241, 109, 122, 0.35);
  border-radius: 5px;
  color: #ff9ca5;
  background: rgba(241, 109, 122, 0.09);
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
}

.shortcut-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 9px;
  color: #8492a8;
  font-size: 10px;
}

.shortcut-grid kbd {
  min-width: 44px;
  padding: 2px 5px;
  border: 1px solid var(--line);
  border-radius: 4px;
  color: #dce8f7;
  background: #09111d;
  text-align: center;
  font-family: Consolas, monospace;
}

.editor-statusbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-top: 1px solid var(--line);
  color: #718097;
  background: #09111d;
  font-family: Consolas, monospace;
  font-size: 10px;
}

.editor-statusbar .ok {
  color: #34d399;
}

.editor-loader {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  color: #dbeafe;
  background: rgba(4, 8, 15, 0.9);
}

.loader-spinner {
  width: 34px;
  height: 34px;
  border: 3px solid rgba(255, 255, 255, 0.14);
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1100px) {
  .editor-workspace {
    grid-template-columns: 210px minmax(420px, 1fr);
  }

  .property-sidebar {
    display: none;
  }
}
</style>
