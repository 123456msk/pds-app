<template>
  <section class="modality-upload" :class="[type, { dragging: isDragging, busy: state.isScanning }]" @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="handleDrop">
    <header class="modality-head"><div class="modality-mark"><span>{{ type === 'mri' ? 'MR' : 'PT' }}</span></div><div><h3>{{ title }}</h3><p>{{ hint }}</p></div><el-tag :type="type === 'mri' ? 'primary' : 'success'" effect="light">{{ badge }}</el-tag></header>
    <button class="drop-zone" type="button" @click="openFilePicker"><el-icon class="upload-icon"><UploadFilled /></el-icon><div><strong>{{ state.isScanning ? '正在扫描 DICOM 序列...' : hint }}</strong><span>{{ description }}</span></div><el-tag :type="feedbackType" effect="plain">{{ feedbackText }}</el-tag></button>
    <div class="upload-actions"><el-button type="primary" :icon="DocumentAdd" @click="openFilePicker">选择文件</el-button><el-button :icon="FolderOpened" @click="openFolderPicker">选择文件夹</el-button><el-button text :icon="Delete" @click="store.resetModality(type)">清空</el-button></div>
    <input ref="fileInput" class="hidden-input" type="file" multiple @change="handleFileChange" /><input ref="folderInput" class="hidden-input" type="file" multiple webkitdirectory directory @change="handleFileChange" />
    <div class="file-metrics"><span><b>{{ state.fileCount }}</b> 已选</span><span><b>{{ state.dicomCount }}</b> DICOM</span><span><b>{{ state.zipCount }}</b> ZIP</span><span><b>{{ state.skippedCount }}</b> 跳过</span></div>
    <el-alert v-if="state.error" class="inline-alert" :title="state.error" type="warning" :closable="false" show-icon />
  </section>
</template>
<script setup>
import { computed, ref } from 'vue';
import { Delete, DocumentAdd, FolderOpened, UploadFilled } from '@element-plus/icons-vue';
import { useUploadStore } from '../stores/uploadStore';
const props = defineProps({ type: { type: String, required: true, validator: value => ['mri','pet'].includes(value) }, title: { type: String, required: true }, badge: { type: String, required: true }, hint: { type: String, required: true }, description: { type: String, required: true } });
const store=useUploadStore();const state=computed(()=>store.modalities[props.type]);const fileInput=ref(null);const folderInput=ref(null);const isDragging=ref(false);
const feedbackText=computed(()=>{if(state.value.isScanning)return '读取元数据中';if(state.value.selectedSeries)return `已识别 ${state.value.selectedSeries.count} 张 ${state.value.selectedSeries.modality}`;if(state.value.scanned)return props.type==='mri'?'未找到 T2 MRI':'未找到 PET 序列';return '等待上传';});
const feedbackType=computed(()=>state.value.selectedSeries?'success':state.value.scanned?'warning':'info');
function openFilePicker(){fileInput.value?.click();}function openFolderPicker(){folderInput.value?.click();}
async function handleFileChange(event){const files=Array.from(event.target.files||[]);event.target.value='';await store.scanModality(props.type,files);}
async function handleDrop(event){isDragging.value=false;await store.scanModality(props.type,Array.from(event.dataTransfer?.files||[]));}
</script>
