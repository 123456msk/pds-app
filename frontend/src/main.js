import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import App from './App.vue';
import router from './router';
import './styles/app.css';

router.afterEach(to => {
  document.title = to.meta.title || 'PDS';
});

createApp(App).use(createPinia()).use(ElementPlus).use(router).mount('#app');
