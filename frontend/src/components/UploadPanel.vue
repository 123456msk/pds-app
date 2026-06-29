<template>
  <section class="workspace">
    <el-steps
      :active="activeStep"
      align-center
      finish-status="success"
      class="workflow-steps"
      ><el-step title="上传影像" /><el-step title="前列腺分割" /><el-step
        title="AI 诊断"
    /></el-steps>

    <section class="clinical-workbench">
      <header class="workbench-header">
        <div>
          <span class="section-index">01</span>
          <div>
            <h2>病例与影像准备</h2>
            <p>填写患者指标并上传 MRI、PSMA PET/CT DICOM 序列。</p>
          </div>
        </div>
        <span class="privacy-note">数据仅保存在本机病例目录</span>
      </header>

      <div class="patient-section">
        <div class="section-label">
          <span>患者资料</span><small>必填</small>
        </div>
        <el-form label-position="top" class="patient-form"
          ><el-row :gutter="16"
            ><el-col :xs="24" :sm="12" :lg="6"
              ><el-form-item label="病人姓名 / Name"
                ><el-input
                  v-model="patient.name"
                  size="large"
                  placeholder="请输入姓名"
                  maxlength="60" /></el-form-item></el-col
            ><el-col :xs="24" :sm="12" :lg="6"
              ><el-form-item label="年龄 / Age (岁)"
                ><el-input-number
                  v-model="patient.age"
                  size="large"
                  :min="0"
                  :max="120"
                  :controls="false"
                  placeholder="例如：65" /></el-form-item></el-col
            ><el-col :xs="24" :sm="12" :lg="6"
              ><el-form-item label="PSA (ng/ml)"
                ><el-input-number
                  v-model="patient.psa"
                  size="large"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  placeholder="例如：8.50" /></el-form-item></el-col
            ><el-col :xs="24" :sm="12" :lg="6"
              ><el-form-item label="f/tPSA"
                ><el-input-number
                  v-model="patient.ftPsa"
                  size="large"
                  :min="0"
                  :precision="3"
                  :controls="false"
                  placeholder="例如：0.160" /></el-form-item></el-col></el-row
        ></el-form>
      </div>

      <div class="workbench-divider"></div>
      <div class="section-label imaging-label">
        <span>影像数据</span><small>支持多文件、文件夹与 ZIP</small>
      </div>
      <div class="modality-grid">
        <div class="modality-lane">
          <ModalityUploadCard
            type="mri"
            title="MRI 影像"
            badge="T2W / DWI / ADC"
            hint="上传 MRI DICOM"
            description="完整 T2W 序列用于前列腺分割。"
          /><SeriesScanResult type="mri" title="MRI 目标序列" />
        </div>
        <div class="modality-lane">
          <ModalityUploadCard
            type="pet"
            title="PSMA PET/CT"
            badge="PET / CT"
            hint="上传 PET/CT DICOM"
            description="PET 与 CT 序列用于跨模态映射。"
          /><SeriesScanResult type="pet" title="PET/CT 目标序列" />
        </div>
      </div>
    </section>

    <section class="clinical-workbench segmentation-workbench">
      <header class="workbench-header">
        <div>
          <span class="section-index">02</span>
          <div>
            <h2>前列腺分割</h2>
            <p>
              设置 MRI 与 CT 前列腺切片范围，提交后执行自动分割与跨模态映射。
            </p>
          </div>
        </div>
        <span class="privacy-note">完整 T2W MRI 用于分割</span>
      </header>
      <div class="range-section">
        <div class="section-label">
          <span>前列腺切片范围</span><small>闭区间，按文件名首个数字</small>
        </div>
        <div class="range-grid">
          <div class="range-row mri">
            <div class="range-row-title">
              <span></span>
              <div>
                <strong>MRI 范围</strong><small>分割后用于裁剪与映射</small>
              </div>
            </div>
            <el-input-number
              v-model="ranges.mri.start"
              :min="0"
              :controls="false"
              placeholder="起始，如 4"
              size="large"
            /><span class="range-separator">至</span
            ><el-input-number
              v-model="ranges.mri.end"
              :min="0"
              :controls="false"
              placeholder="结束，如 17"
              size="large"
            />
          </div>
          <div class="range-row pet">
            <div class="range-row-title">
              <span></span>
              <div>
                <strong>CT 范围</strong><small>{{ petRangeText }}</small>
              </div>
            </div>
            <el-input-number
              v-model="ranges.ct.start"
              :min="0"
              :controls="false"
              placeholder="起始，如 563"
              size="large"
            /><span class="range-separator">至</span
            ><el-input-number
              v-model="ranges.ct.end"
              :min="0"
              :controls="false"
              placeholder="结束，如 591"
              size="large"
            />
          </div>
        </div>
      </div>
      <footer class="workbench-action">
        <div>
          <strong>{{
            seriesReady ? "影像准备完成" : "等待 MRI 与 PET/CT 序列"
          }}</strong
          ><span>{{
            seriesReady
              ? "可以提交完整影像并开始自动分割。"
              : "上传后系统会自动识别 T2W、PET 与 CT。"
          }}</span>
        </div>
        <el-button
          class="segment-button"
          type="primary"
          size="large"
          :loading="isSubmitting"
          :disabled="!seriesReady || sessionLocked"
          :icon="Aim"
          @click="handleSubmit"
          >{{
            sessionLocked ? "分割与映射已完成" : "开始分割与映射"
          }}</el-button
        >
      </footer>
    </section>

    <section v-if="hasCompletedResults" class="result-actions">
      <div>
        <el-icon><CircleCheckFilled /></el-icon>
        <div>
          <strong>分割与映射已完成</strong
          ><span>{{ completedPatientLabel }} · 已生成 12 个 NIfTI 文件</span>
        </div>
      </div>
      <div class="result-action-buttons">
        <el-button :icon="Download" @click="downloadResults">下载结果</el-button
        ><el-button type="primary" :icon="View" @click="openStandaloneViewer"
          >打开阅片器</el-button
        ><el-button
          type="success"
          :icon="DataAnalysis"
          :loading="diagnosisLoading"
          @click="startDiagnosis"
          >开始诊断</el-button
        ><el-button :icon="RefreshRight" @click="restartFlow"
          >重新开始</el-button
        >
      </div>
    </section>

    <section v-if="hasCompletedResults" class="result-download-panel">
      <div class="result-download-header">
        <div>
          <strong>结果文件下载</strong>
          <span>12 个 NIfTI 文件，可按需勾选打包下载。</span>
        </div>
        <div class="result-file-actions">
          <el-button size="small" @click="selectAllResultFiles">全选</el-button>
          <el-button size="small" @click="selectedResultFiles = []">清空</el-button>
        </div>
      </div>
      <el-checkbox-group v-model="selectedResultFiles" class="result-file-grid">
        <el-checkbox
          v-for="filename in resultFiles"
          :key="filename"
          :label="filename"
          border
        >
          {{ filename }}
        </el-checkbox>
      </el-checkbox-group>
      <div class="result-download-actions">
        <el-button
          :icon="Download"
          :loading="selectedDownloadLoading"
          @click="downloadSelectedResults('current')"
        >
          下载当前结果
        </el-button>
        <el-button
          :icon="Download"
          :loading="selectedDownloadLoading"
          @click="downloadSelectedResults('before')"
        >
          下载修改前结果
        </el-button>
        <el-button
          v-if="hasEditedResults"
          type="primary"
          :icon="Download"
          :loading="selectedDownloadLoading"
          @click="downloadSelectedResults('edited')"
        >
          下载编辑后结果
        </el-button>
      </div>
      <el-alert
        v-if="hasEditedResults"
        class="edited-result-tip"
        type="success"
        :closable="false"
        show-icon
        title="已检测到阅片器保存过修改；编辑后下载会导出当前病例最新结果。"
      />
    </section>

    <DiagnosisReport
      v-if="diagnosisStarted"
      id="diagnosis-report"
      :patient="completedPatient"
      :case-id="preparedResult?.case_id || ''"
      :slice-counts="sliceCounts"
      :prediction="diagnosisResult"
      :loading="diagnosisLoading"
      :error="diagnosisError"
    />
    <el-dialog
      v-model="resultDialogVisible"
      title="分割与映射结果"
      width="min(720px, 94vw)"
      ><el-alert
        :title="'病例 ' + (preparedResult?.case_id || '') + ' 已生成 12 个文件'"
        type="success"
        :closable="false"
        show-icon
      /><el-descriptions :column="1" border size="small"
        ><el-descriptions-item label="患者">{{
          completedPatientLabel
        }}</el-descriptions-item
        ><el-descriptions-item label="MRI 模型输入"
          >完整 T2W MRI，{{
            preparedResult?.volumes?.mri?.source_count || 0
          }}
          张</el-descriptions-item
        ><el-descriptions-item label="MRI / CT / PET 输出切片">{{
          sliceCounts
        }}</el-descriptions-item
        ><el-descriptions-item label="结果文件数">{{
          segmentationResult?.segmentation?.multimodal?.file_count || 0
        }}</el-descriptions-item></el-descriptions
      ><template #footer
        ><el-button :icon="Download" @click="downloadResults"
          >下载结果</el-button
        ><el-button type="primary" :icon="View" @click="openViewerFromDialog"
          >打开阅片器</el-button
        ></template
      ></el-dialog
    >

    <transition name="loading-fade"
      ><div v-if="isSubmitting" class="package-loading-overlay" role="status">
        <div class="package-loading-panel">
          <div class="medical-spinner"><span></span></div>
          <strong>正在处理医学影像</strong>
          <p>{{ submitStatus }}</p>
          <div class="loading-track"><div class="loading-track-bar"></div></div>
          <small>完整 3D 分割和跨模态映射耗时较长，请保持页面打开</small>
        </div>
      </div></transition
    >
  </section>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  Aim,
  CircleCheckFilled,
  DataAnalysis,
  Download,
  FolderChecked,
  RefreshRight,
  View,
} from "@element-plus/icons-vue";
import DiagnosisReport from "./DiagnosisReport.vue";
import ModalityUploadCard from "./ModalityUploadCard.vue";
import SeriesScanResult from "./SeriesScanResult.vue";
import { useUploadStore } from "../stores/uploadStore";
import {
  apiUrl,
  downloadResultBlob,
  fetchCaseManifest,
  originalResultFileUrl,
  predictPreparedCase,
  prepareCaseOnBackend,
  resultFileUrl,
  segmentPreparedCase,
} from "../api/casePreparation";
import JSZip from "jszip";

const store = useUploadStore();
const patient = reactive({ name: "", age: null, psa: null, ftPsa: null });
const ranges = reactive({
  mri: { start: 4, end: 17 },
  ct: { start: 563, end: 591 },
});
const isSubmitting = ref(false);
const submitStatus = ref("正在初始化...");
const resultDialogVisible = ref(false);
const preparedResult = ref(null);
const segmentationResult = ref(null);
const completedRevision = ref(null);
const completedPatient = ref({});
const sessionLocked = ref(false);
const diagnosisStarted = ref(false);
const diagnosisLoading = ref(false);
const diagnosisResult = ref(null);
const diagnosisError = ref("");
const selectedDownloadLoading = ref(false);
const hasEditedResults = ref(false);
const resultFiles = [
  "mri.nii.gz",
  "mripz_mask.nii.gz",
  "mritz_mask.nii.gz",
  "mriwg_mask.nii.gz",
  "ct.nii.gz",
  "ctpz_mask.nii.gz",
  "cttz_mask.nii.gz",
  "ctwg_mask.nii.gz",
  "pet.nii.gz",
  "petpz_mask.nii.gz",
  "pettz_mask.nii.gz",
  "petwg_mask.nii.gz",
];
const selectedResultFiles = ref([...resultFiles]);

const seriesReady = computed(() => {
  const mri = store.modalities.mri;
  const psma = store.modalities.pet;
  return Boolean(
    mri.scanned &&
      psma.scanned &&
      mri.selectedSeries &&
      psma.selectedSeries &&
      psma.ctSeries &&
      !mri.isScanning &&
      !psma.isScanning
  );
});
const hasCompletedResults = computed(
  () =>
    sessionLocked.value &&
    segmentationResult.value?.segmentation?.multimodal?.file_count === 12
);
const activeStep = computed(() =>
  diagnosisStarted.value
    ? 3
    : hasCompletedResults.value
    ? 2
    : isSubmitting.value || seriesReady.value
    ? 1
    : 0
);
const completedPatientLabel = computed(() => {
  const value = completedPatient.value;
  if (!value?.name) return "--";
  return `${value.name} · ${value.age} 岁 · PSA ${value.psa} ng/ml · f/tPSA ${value.ftPsa}`;
});
const petRangeText = computed(() => {
  const ct = store.modalities.pet.ctSeries?.count || 0;
  const pet = store.modalities.pet.selectedSeries?.count || 0;
  if (!ct || !pet) return "识别 CT 与 PET 后自动显示";
  return `CT ${ct} 张 / PET ${pet} 张，PET 范围约为 ${Math.max(
    1,
    Math.round((ranges.ct.start * pet) / ct)
  )}-${Math.min(pet, Math.round((ranges.ct.end * pet) / ct))}`;
});
const sliceCounts = computed(() => {
  const value =
    segmentationResult.value?.segmentation?.multimodal?.slice_counts;
  return value ? `MRI ${value.mri} / CT ${value.ct} / PET ${value.pet}` : "--";
});

function validateInputs() {
  if (!patient.name.trim()) throw new Error("请输入病人姓名。");
  if (!Number.isInteger(patient.age) || patient.age < 0 || patient.age > 120)
    throw new Error("请输入有效年龄。");
  if (!Number.isFinite(patient.psa) || patient.psa < 0)
    throw new Error("请输入有效 PSA。");
  if (!Number.isFinite(patient.ftPsa) || patient.ftPsa < 0)
    throw new Error("请输入有效 f/tPSA。");
  for (const [label, range] of [
    ["MRI", ranges.mri],
    ["CT", ranges.ct],
  ]) {
    if (!Number.isInteger(range.start) || !Number.isInteger(range.end))
      throw new Error(label + " 起止序号必须填写整数。");
    if (range.start > range.end)
      throw new Error(label + " 起始序号不能大于结束序号。");
  }
}
function downloadResults() {
  const caseId = preparedResult.value?.case_id;
  if (caseId)
    window.open(apiUrl(`/cases/${caseId}/results`), "_blank");
}
function openStandaloneViewer() {
  const caseId = preparedResult.value?.case_id;
  if (caseId)
    window.open(`/image-editor?case_id=${encodeURIComponent(caseId)}&from=diagnosis`, "_blank");
}
function openViewerFromDialog() {
  resultDialogVisible.value = false;
  openStandaloneViewer();
}
function editedStorageKey(caseId) {
  return `pds_case_${caseId}_edited`;
}
async function refreshEditedResultState() {
  const caseId = preparedResult.value?.case_id;
  if (!caseId) {
    hasEditedResults.value = false;
    return;
  }
  if (localStorage.getItem(editedStorageKey(caseId))) {
    hasEditedResults.value = true;
    return;
  }
  try {
    const manifest = await fetchCaseManifest(caseId);
    hasEditedResults.value = Boolean(manifest.viewer_edits?.saved_at);
    if (hasEditedResults.value) {
      localStorage.setItem(editedStorageKey(caseId), manifest.viewer_edits.saved_at);
    }
  } catch {
    hasEditedResults.value = false;
  }
}
function handleWindowFocus() {
  if (hasCompletedResults.value) refreshEditedResultState();
}
function handleStorageChange(event) {
  const caseId = preparedResult.value?.case_id;
  if (caseId && event.key === editedStorageKey(caseId)) hasEditedResults.value = Boolean(event.newValue);
}
function selectAllResultFiles() {
  selectedResultFiles.value = [...resultFiles];
}
async function downloadSelectedResults(kind = "current") {
  const caseId = preparedResult.value?.case_id;
  if (!caseId || selectedDownloadLoading.value) return;
  if (!selectedResultFiles.value.length) {
    ElMessage.warning("请至少选择一个结果文件。");
    return;
  }
  selectedDownloadLoading.value = true;
  try {
    const zip = new JSZip();
    for (const filename of selectedResultFiles.value) {
      const url = kind === "before" ? originalResultFileUrl(caseId, filename) : resultFileUrl(caseId, filename);
      zip.file(filename, await downloadResultBlob(url));
    }
    const blob = await zip.generateAsync({ type: "blob", compression: "STORE" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const suffix = kind === "before" ? "before_edit" : kind === "edited" ? "edited" : "current";
    link.download = `${caseId}_${suffix}_results.zip`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  } catch (error) {
    ElMessage.error(error.message || "下载结果失败。");
  } finally {
    selectedDownloadLoading.value = false;
  }
}
async function startDiagnosis() {
  const caseId = preparedResult.value?.case_id;
  if (!caseId || diagnosisLoading.value) return;
  await refreshEditedResultState();
  diagnosisStarted.value = true;
  diagnosisLoading.value = true;
  diagnosisResult.value = null;
  diagnosisError.value = "";
  resultDialogVisible.value = false;
  await nextTick();
  document
    .getElementById("diagnosis-report")
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    diagnosisResult.value = await predictPreparedCase(caseId);
    ElMessage.success("AI 预测完成。");
  } catch (error) {
    diagnosisError.value = error.message || "AI 预测失败。";
    ElMessage.error(diagnosisError.value);
  } finally {
    diagnosisLoading.value = false;
  }
}
function restartFlow() {
  store.resetAll();
  patient.name = "";
  patient.age = null;
  patient.psa = null;
  patient.ftPsa = null;
  ranges.mri.start = 4;
  ranges.mri.end = 17;
  ranges.ct.start = 563;
  ranges.ct.end = 591;
  preparedResult.value = null;
  segmentationResult.value = null;
  completedPatient.value = {};
  completedRevision.value = null;
  sessionLocked.value = false;
  diagnosisStarted.value = false;
  resultDialogVisible.value = false;
  hasEditedResults.value = false;
  ElMessage.info("已清空当前病例，可以重新上传影像。");
}
async function handleSubmit() {
  try {
    validateInputs();
    isSubmitting.value = true;
    submitStatus.value = "正在打包全部 DICOM 文件...";
    await nextTick();
    const patientPayload = {
      name: patient.name.trim(),
      age: patient.age,
      psa: patient.psa,
      ftPsa: patient.ftPsa,
    };
    preparedResult.value = await prepareCaseOnBackend(
      store.modalities,
      { mri: { ...ranges.mri }, ct: { ...ranges.ct } },
      patientPayload,
      (status) => {
        submitStatus.value = status;
      }
    );
    submitStatus.value = "正在运行完整 MRI 分割并映射到 CT/PET...";
    segmentationResult.value = await segmentPreparedCase(
      preparedResult.value.case_id,
      (status) => {
        submitStatus.value = status;
      }
    );
    completedPatient.value = patientPayload;
    completedRevision.value = store.revision;
    sessionLocked.value = true;
    hasEditedResults.value = false;
    resultDialogVisible.value = true;
    refreshEditedResultState();
    ElMessage.success("已生成 12 个结果文件。");
  } catch (error) {
    ElMessage.error(error.message || "自动分割失败。");
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(() => {
  window.addEventListener("focus", handleWindowFocus);
  window.addEventListener("storage", handleStorageChange);
});

onBeforeUnmount(() => {
  window.removeEventListener("focus", handleWindowFocus);
  window.removeEventListener("storage", handleStorageChange);
});
</script>

<style scoped>
.patient-form :deep(.el-input-number .el-input__inner) {
  text-align: left;
}

.workbench-action {
  border-top: 1px solid #dce8f2;
  background:
    linear-gradient(90deg, rgba(7, 136, 199, 0.08), rgba(22, 163, 106, 0.08)),
    #f8fbfe;
}

.segment-button {
  min-width: 230px;
  height: 48px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, #0689c8 0%, #16a36a 100%);
  box-shadow: 0 12px 24px rgba(7, 136, 199, 0.22);
  font-size: 15px;
  font-weight: 900;
}

.segment-button:not(.is-disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 30px rgba(7, 136, 199, 0.28);
}

.segment-button.is-disabled {
  border: 1px solid #d4dfeb;
  background: #edf3f8;
  box-shadow: none;
  color: #8b99aa;
}

.result-download-panel {
  margin-top: -12px;
  padding: 18px;
  border: 1px solid #d9e4f2;
  border-radius: 10px;
  background: linear-gradient(180deg, #fbfdff 0%, #f4f8fc 100%);
}

.result-download-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.result-download-header strong {
  display: block;
  color: #12345b;
  font-size: 16px;
}

.result-download-header span {
  color: #6a7b91;
  font-size: 12px;
}

.result-file-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.result-file-grid :deep(.el-checkbox) {
  min-width: 0;
  margin-right: 0;
}

.result-file-grid :deep(.el-checkbox__label) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-file-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.result-download-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.edited-result-tip {
  margin-top: 12px;
}
</style>
