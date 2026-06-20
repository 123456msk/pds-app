<template>
  <el-card class="diagnosis-report" shadow="never">
    <template #header>
      <div class="diagnosis-report-head">
        <div><span class="report-kicker">PDS AI DIAGNOSTIC REPORT</span><h2>前列腺多模态 AI 诊断报告单</h2><p>报告编号：{{ reportNumber }} · 生成时间：{{ generatedAt }}</p></div>
        <el-button :icon="Printer" @click="printReport">打印报告</el-button>
      </div>
    </template>
    <el-descriptions :column="4" border class="report-patient-grid">
      <el-descriptions-item label="姓名">{{ patient.name || '--' }}</el-descriptions-item><el-descriptions-item label="年龄">{{ patient.age ?? '--' }} 岁</el-descriptions-item><el-descriptions-item label="PSA">{{ patient.psa ?? '--' }} ng/ml</el-descriptions-item><el-descriptions-item label="f/tPSA">{{ patient.ftPsa ?? '--' }}</el-descriptions-item>
    </el-descriptions>
    <div class="report-section"><h3>影像处理摘要</h3><div class="report-status-grid"><div><span>分割与映射</span><strong class="status-success">已完成</strong></div><div><span>结果文件</span><strong>12 个 NIfTI</strong></div><div><span>阅片掩膜</span><strong>MRI / PET：PZ、TZ</strong></div><div><span>切片统计</span><strong>{{ sliceCounts }}</strong></div></div></div>
    <div class="report-section"><h3>AI 风险评估</h3><div class="report-metric-grid"><div class="report-metric"><span>恶性概率</span><strong>--</strong><small>等待预测模型</small></div><div class="report-metric"><span>风险分层</span><strong>待分析</strong><small>等待预测模型</small></div><div class="report-metric"><span>Gleason 预测</span><strong>--</strong><small>等待预测模型</small></div></div></div>
    <el-alert title="AI 预测接口尚未接入" type="warning" :closable="false" show-icon>当前报告已汇总患者信息和分割结果。接入预测模型后，此处将显示癌症风险、分级及综合诊断意见。</el-alert>
    <div class="report-signature"><div><span>AI 分析状态</span><strong>等待模型结果</strong></div><div><span>病例编号</span><strong>{{ caseId }}</strong></div></div>
    <p class="report-disclaimer">本报告为人工智能辅助分析结果，仅供临床医生参考，不可替代病理检查及临床诊断。</p>
  </el-card>
</template>
<script setup>
import { computed } from 'vue';
import { Printer } from '@element-plus/icons-vue';
const props = defineProps({ patient: { type: Object, required: true }, caseId: { type: String, required: true }, sliceCounts: { type: String, default: '--' } });
const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });
const reportNumber = computed(() => `PDS-${props.caseId.replace(/^case_/, '') || 'AUTO'}`);
function printReport() { window.print(); }
</script>
