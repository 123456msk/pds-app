<template>
  <section class="series-result">
    <header class="series-result-head"><div><span class="series-kicker">序列识别</span><h4>{{ title }}</h4></div><el-tag :type="stateTagType" effect="light">{{ stateLabel }}</el-tag></header>
    <el-skeleton v-if="state.isScanning" :rows="3" animated />
    <template v-else-if="state.scanned">
      <div v-if="state.selectedSeries" class="selected-series"><el-icon><CircleCheckFilled /></el-icon><div><strong>{{ selectedTitle }}</strong><span>{{ state.selectedSeries.modality || 'UNKNOWN' }} · {{ state.selectedSeries.count }} 张 · UID {{ shortUid(state.selectedSeries.uid) }}</span></div></div>
      <el-alert v-else :title="missingMessage" type="warning" :closable="false" show-icon />
      <div v-if="type === 'pet' && state.ctSeries" class="retained-series"><span>CT</span><div><strong>已保留 CT 序列</strong><small>{{ state.ctSeries.count }} 张 · {{ state.ctSeries.description }}</small></div></div>
      <el-collapse v-if="state.series.length" class="series-collapse"><el-collapse-item :title="`查看全部 ${state.series.length} 个序列`"><el-table :data="sortedSeries" size="small" max-height="280" row-key="uid"><el-table-column label="状态" width="82"><template #default="{ row }"><el-tag v-if="state.selectedSeries?.uid === row.uid" type="success" size="small">选中</el-tag><el-tag v-else-if="type === 'pet' && state.ctSeries?.uid === row.uid" type="info" size="small">CT</el-tag><el-tag v-else size="small" effect="plain">排除</el-tag></template></el-table-column><el-table-column prop="modality" label="类型" width="72" /><el-table-column prop="count" label="张数" width="72" /><el-table-column prop="description" label="序列描述" min-width="180" show-overflow-tooltip /></el-table></el-collapse-item></el-collapse>
    </template>
    <div v-else class="series-placeholder"><span></span>上传后自动识别目标序列</div>
  </section>
</template>
<script setup>
import { computed } from 'vue';import { CircleCheckFilled } from '@element-plus/icons-vue';import { useUploadStore } from '../stores/uploadStore';
const props=defineProps({type:{type:String,required:true,validator:value=>['mri','pet'].includes(value)},title:{type:String,required:true}});const store=useUploadStore();const state=computed(()=>store.modalities[props.type]);
const sortedSeries=computed(()=>[...state.value.series].sort((a,b)=>{const as=state.value.selectedSeries?.uid===a.uid||state.value.ctSeries?.uid===a.uid;const bs=state.value.selectedSeries?.uid===b.uid||state.value.ctSeries?.uid===b.uid;if(as!==bs)return as?-1:1;if(a.matches!==b.matches)return a.matches?-1:1;return b.count-a.count;}));
const selectedTitle=computed(()=>props.type==='mri'?`T2W：${state.value.selectedSeries.description}`:`PET：${state.value.selectedSeries.description}`);const stateLabel=computed(()=>state.value.isScanning?'扫描中':state.value.selectedSeries?'已识别':state.value.scanned?'未命中':'等待上传');const stateTagType=computed(()=>state.value.selectedSeries?'success':state.value.scanned?'warning':state.value.isScanning?'primary':'info');const missingMessage=computed(()=>props.type==='mri'?'未找到 T2 MRI 序列。':'未找到 PET (PT) 序列。');function shortUid(uid){if(!uid)return '--';return uid.length>16?`${uid.slice(0,8)}...${uid.slice(-6)}`:uid;}
</script>
