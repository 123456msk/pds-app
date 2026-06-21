<template>
  <main class="app-shell">
    <nav class="topbar">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true">
          <span class="logo-core">P</span>
        </div>
        <div>
          <div class="brand-title">前列腺 MRI 智能分割诊断</div>
          <!-- <div class="brand-subtitle">MRI · PSMA PET/CT · AI 辅助诊断</div> -->
        </div>
      </div>
      <div class="system-status"><span></span>V4.0 · DCM 系统</div>
      <!-- <el-tag effect="plain" size="large">v4.0 · DCM</el-tag> -->
    </nav>
    <header class="page-intro">
      <h1>前列腺 MRI 智能分割诊断</h1>
      <p>
        支持 DICOM (.dcm) 格式的核磁共振影像。上传 MRI 和/或 PSMA PET/CT 的 DCM 文件，
        系统自动识别前列腺区域、分割前列腺掩膜、生成精准风险报告。
      </p>
    </header>


    <UploadPanel />
  </main>
</template>
<script setup>
import UploadPanel from "./components/UploadPanel.vue";
</script>

