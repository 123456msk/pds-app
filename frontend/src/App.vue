<template>
  <main class="app-shell">
    <nav class="topbar">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true"><span class="logo-core">P</span></div>
        <div><div class="brand-title">前列腺 MRI 智能分割诊断</div><div class="brand-subtitle">MRI · PSMA PET/CT · AI 辅助诊断</div></div>
      </div>
      <div class="system-status"><span></span>系统就绪</div>
    </nav>
    <header class="page-intro">
      <div><span class="page-eyebrow">PDS CLINICAL WORKSPACE</span><h1>前列腺多模态影像工作台</h1><p>上传 DICOM 序列，完成 T2W 识别、前列腺分区分割、跨模态映射与诊断报告。</p></div>
      <el-tag effect="plain" size="large">v4.0 · DCM</el-tag>
    </header>
    <UploadPanel />
  </main>
</template>
<script setup>
import UploadPanel from './components/UploadPanel.vue';
</script>
