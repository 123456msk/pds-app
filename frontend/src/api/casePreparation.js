import JSZip from 'jszip';
import { apiUrl, http } from './http';

export { apiUrl };

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
  const { data } = await http.post('/cases/prepare', formData);
  return data;
}

export async function segmentPreparedCase(caseId, onProgress) {
  onProgress?.('正在运行完整 T2 MRI 分割并映射到 CT/PET');
  const { data } = await http.post(`/cases/${caseId}/segment`);
  return data;
}
export function resultFileUrl(caseId, filename) {
  return `/cases/${caseId}/results/${encodeURIComponent(filename)}`;
}

export function originalResultFileUrl(caseId, filename) {
  return `/cases/${caseId}/results-original/${encodeURIComponent(filename)}`;
}

export async function fetchCaseManifest(caseId) {
  const { data } = await http.get(`/cases/${encodeURIComponent(caseId)}`);
  return data;
}

export async function saveViewerMasks(caseId, payloads) {
  const formData = new FormData();
  for (const [field, blob] of Object.entries(payloads)) {
    formData.append(field, blob, `${field}.nii.gz`);
  }
  const { data } = await http.post(`/cases/${caseId}/viewer-masks`, formData);
  return data;
}

export async function predictPreparedCase(caseId) {
  const { data } = await http.post(`/cases/${caseId}/predict`);
  return data;
}

export async function downloadResultBlob(url) {
  const { data } = await http.get(url, { responseType: 'blob' });
  return data;
}

export async function downloadResultArrayBuffer(url) {
  const { data } = await http.get(url, { responseType: 'arraybuffer' });
  return data;
}
