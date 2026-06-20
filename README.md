# PDS 前列腺 MRI 智能分割诊断

Vue 3 + FastAPI 前列腺多模态影像工作台，支持 MRI、PSMA PET/CT DICOM 序列识别、前列腺 WG/PZ/TZ 分割、MRI 到 CT/PET 映射、双模态阅片与诊断报告。

## 目录

- `frontend/`：Vue 3、Vite、Element Plus 前端。
- `backend/`：FastAPI、nnU-Net 分割与多模态映射服务。
- 模型权重使用 Git LFS 管理。

## 启动

```powershell
cd backend
.\.venv\python.exe -X utf8 run.py
```

```powershell
cd frontend
npm install
npm run dev
```

前端默认地址：`http://127.0.0.1:5173/`  
后端默认地址：`http://127.0.0.1:8100/`
