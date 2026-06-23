<template>
  <el-card class="diagnosis-report" shadow="never">
    <template #header>
      <div class="diagnosis-report-head">
        <div>
          <div class="report-title-row"><span class="section-index">03</span><h2>前列腺多模态 AI 诊断报告单</h2></div>
          <p>报告编号：{{ reportNumber }} · 生成时间：{{ generatedAt }}</p>
        </div>
        <el-button :icon="Printer" @click="printReport">打印报告</el-button>
      </div>
    </template>

    <el-descriptions :column="4" border class="report-patient-grid">
      <el-descriptions-item label="姓名">{{ patient.name || '--' }}</el-descriptions-item>
      <el-descriptions-item label="年龄">{{ patient.age ?? '--' }} 岁</el-descriptions-item>
      <el-descriptions-item label="PSA">{{ patient.psa ?? '--' }} ng/ml</el-descriptions-item>
      <el-descriptions-item label="f/tPSA">{{ patient.ftPsa ?? '--' }}</el-descriptions-item>
    </el-descriptions>

    <div class="report-section">
      <h3>影像处理摘要</h3>
      <div class="report-status-grid">
        <div><span>分割与映射</span><strong class="status-success">已完成</strong></div>
        <div><span>结果文件</span><strong>12 个 NIfTI</strong></div>
        <div><span>模型输入</span><strong>PZ / TZ + 临床指标</strong></div>
        <div><span>切片统计</span><strong>{{ sliceCounts }}</strong></div>
      </div>
    </div>

    <div class="report-section probability-section">
      <h3>AI 风险评估</h3>
      <div v-if="loading" class="probability-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <div><strong>正在计算恶性概率</strong><span>正在提取 PZ/TZ 影像组学特征并运行 预测 模型</span></div>
      </div>
      <el-alert v-else-if="error" :title="error" type="error" :closable="false" show-icon />
      <div v-else-if="prediction" class="probability-result">
        <div class="probability-ring" :style="ringStyle"><strong>{{ probabilityText }}</strong><span>恶性概率</span></div>
        <div class="probability-copy"><span>多模态预测</span><strong>{{ probabilityText }}</strong><small>模型输入 {{ prediction.feature_count }} 项特征。</small></div>
      </div>
    </div>

    <div class="report-signature">
      <div><span>AI 分析状态</span><strong>{{ loading ? '分析中' : prediction ? '预测完成' : '等待结果' }}</strong></div>
      <div><span>病例编号</span><strong>{{ caseId }}</strong></div>
    </div>
    <p class="report-disclaimer">本报告为人工智能辅助分析结果，仅供临床医生参考，不可替代病理检查及临床诊断。</p>
  </el-card>
</template>

<script setup>
import { computed } from 'vue';
import { Loading, Printer } from '@element-plus/icons-vue';

const props = defineProps({
  patient: { type: Object, required: true },
  caseId: { type: String, required: true },
  sliceCounts: { type: String, default: '--' },
  prediction: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
});

const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });
const reportNumber = computed(() => `PDS-${props.caseId.replace(/^case_/, '') || 'AUTO'}`);
const probabilityText = computed(() => props.prediction ? `${props.prediction.probability_percent.toFixed(2)}%` : '--');
const ringStyle = computed(() => {
  const probability = Math.max(0, Math.min(100, props.prediction?.probability_percent || 0));
  return { background: `conic-gradient(#0788c7 ${probability}%, #e6edf5 ${probability}% 100%)` };
});
function printReport() { window.print(); }
</script>
