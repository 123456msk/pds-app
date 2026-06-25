import JSZip from 'jszip';

async function buildDicomZip(entries, label, onProgress) {
  if (!entries.length) {
    throw new Error(`${label} 没有可提交的 DICOM 文件。`);
  }
  const zip = new JSZip();
  for (const entry of entries) {
    zip.file(entry.path, entry.buffer);
  }
  return zip.generateAsync(
    { type: 'blob', compression: 'STORE' },
    (metadata) => onProgress?.(`正在打包 ${label} DICOM（${Math.round(metadata.percent)}%）`),
  );
}

export async function prepareCaseOnBackend(modalities, ranges, patient, onProgress) {
  onProgress?.('正在打包全部 MRI DICOM');
  const mriZip = await buildDicomZip(modalities.mri.dicomEntries, 'MRI', onProgress);
  onProgress?.('正在打包全部 PSMA PET/CT DICOM');
  const psmaZip = await buildDicomZip(modalities.pet.dicomEntries, 'PSMA PET/CT', onProgress);

  const caseId = `case_${Date.now()}`;
  const formData = new FormData();
  formData.append('mri_zip', mriZip, 'mri.zip');
  formData.append('psma_zip', psmaZip, 'psma.zip');
  formData.append('start_mri', String(ranges.mri.start));
  formData.append('end_mri', String(ranges.mri.end));
  formData.append('start_ct', String(ranges.ct.start));
  formData.append('end_ct', String(ranges.ct.end));
  formData.append('patient_name', patient.name.trim());
  formData.append('age', String(patient.age));
  formData.append('psa', String(patient.psa));
  formData.append('ft_psa', String(patient.ftPsa));
  formData.append('case_id', caseId);

  onProgress?.('正在上传全部影像并识别序列');
  const response = await fetch('http://127.0.0.1:8100/api/cases/prepare', {
    method: 'POST',
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || '后端病例保存失败。');
  }
  return payload;
}

export async function segmentPreparedCase(caseId, onProgress) {
  onProgress?.('正在运行完整 T2 MRI 分割并映射到 CT/PET');
  const response = await fetch(`http://127.0.0.1:8100/api/cases/${caseId}/segment`, { method: 'POST' });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || '自动分割失败。');
  return payload;
}
export function resultFileUrl(caseId, filename) {
  return `http://127.0.0.1:8100/api/cases/${caseId}/results/${encodeURIComponent(filename)}`;
}

export function originalResultFileUrl(caseId, filename) {
  return `http://127.0.0.1:8100/api/cases/${caseId}/results-original/${encodeURIComponent(filename)}`;
}

export async function fetchCaseManifest(caseId) {
  const response = await fetch(`http://127.0.0.1:8100/api/cases/${encodeURIComponent(caseId)}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || '读取病例信息失败。');
  return payload;
}

export async function saveViewerMasks(caseId, payloads) {
  const formData = new FormData();
  for (const [field, blob] of Object.entries(payloads)) {
    formData.append(field, blob, `${field}.nii.gz`);
  }
  const response = await fetch(`http://127.0.0.1:8100/api/cases/${caseId}/viewer-masks`, {
    method: 'POST',
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || '保存编辑后的掩膜失败。');
  return payload;
}

export async function predictPreparedCase(caseId) {
  const response = await fetch(`http://127.0.0.1:8100/api/cases/${caseId}/predict`, { method: 'POST' });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || 'AI 预测失败。');
  return payload;
}
