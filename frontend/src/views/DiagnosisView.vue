<template>
  <main class="app-shell">
    <nav class="topbar">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true">
          <span class="logo-core">P</span>
        </div>
        <div class="brand-title">前列腺多模态智能诊断系统</div>
      </div>
      <div class="diagnosis-nav-actions">
        <router-link class="editor-entry" to="/image-editor">图像编辑器</router-link>
        <div class="system-status"><span></span>V4.0 · DCM 系统</div>
      </div>
    </nav>

    <header class="page-intro">
      <h1>前列腺多模态智能诊断系统</h1>
      <p>
        支持 DICOM (.dcm) 格式的核磁共振影像。上传 MRI 和/或 PSMA PET/CT 的 DCM 文件，
        系统自动识别前列腺区域、分割前列腺掩膜、生成精准风险报告。
      </p>
    </header>

    <UploadPanel />
  </main>
</template>

<script setup>
import UploadPanel from '../components/UploadPanel.vue';
</script>

<style scoped>
.diagnosis-nav-actions {
  display: flex;
  align-items: center;
  gap: 18px;
}

.editor-entry {
  padding: 7px 12px;
  border: 1px solid #cbd9ea;
  border-radius: 6px;
  color: #185b91;
  background: rgba(255, 255, 255, 0.64);
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}
</style>
