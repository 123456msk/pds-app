import { createRouter, createWebHistory } from 'vue-router';
import DiagnosisView from '../views/DiagnosisView.vue';
import ImageEditorView from '../views/ImageEditorView.vue';

export default createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      alias: '/diagnosis',
      name: 'diagnosis',
      component: DiagnosisView,
      meta: { title: '前列腺多模态智能诊断系统' },
    },
    {
      path: '/image-editor',
      name: 'image-editor',
      component: ImageEditorView,
      meta: { title: 'PDS 图像掩膜编辑器' },
    },
  ],
});
