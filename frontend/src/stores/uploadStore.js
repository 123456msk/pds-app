import { defineStore } from 'pinia';
import { useDicomScanner } from '../composables/useDicomScanner';

function createModalityState() {
  return {
    fileCount: 0,
    zipCount: 0,
    dicomCount: 0,
    skippedCount: 0,
    series: [],
    selectedSeries: null,
    ctSeries: null,
    dicomEntries: [],
    errors: [],
    error: '',
    isScanning: false,
    scanned: false,
  };
}

export const useUploadStore = defineStore('upload', {
  state: () => ({
    revision: 0,
    modalities: {
      mri: createModalityState(),
      pet: createModalityState(),
    },
  }),
  actions: {
    async scanModality(type, files) {
      this.revision += 1;
      const target = this.modalities[type];
      Object.assign(target, createModalityState(), {
        fileCount: files.length,
        isScanning: true,
      });

      if (!files.length) {
        Object.assign(target, {
          isScanning: false,
          scanned: true,
          error: '没有选择文件。',
        });
        return;
      }

      try {
        const { scanFiles } = useDicomScanner();
        const result = await scanFiles(type, files);
        Object.assign(target, result, {
          isScanning: false,
          scanned: true,
          error: result.dicomCount ? '' : '没有找到可解析的 DICOM 文件。',
        });
      } catch (error) {
        Object.assign(target, {
          isScanning: false,
          scanned: true,
          error: error.message || '扫描失败。',
        });
      }
    },
    resetModality(type) {
      this.revision += 1;
      this.modalities[type] = createModalityState();
    },
    resetAll() {
      this.revision += 1;
      this.modalities.mri = createModalityState();
      this.modalities.pet = createModalityState();
    },
  },
});
