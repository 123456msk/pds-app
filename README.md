# PDS 前列腺 MRI 智能分割诊断

## 一键安装并运行

Windows PowerShell：

```powershell
python .\start.py
```

macOS / Linux：

```bash
python3 start.py
```

脚本会自动安装后端依赖、前端依赖，并同时启动：

- 后端：`http://127.0.0.1:8100/`
- 前端：`http://127.0.0.1:5173/`

按 `Ctrl+C` 可以同时停止前后端服务。

## 手动安装后端

Windows PowerShell：

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS / Linux：

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 手动运行后端

Windows PowerShell：

```powershell
cd backend
.\.venv\python.exe -X utf8 run.py
```

macOS / Linux：

```bash
cd backend
source .venv/bin/activate
python -X utf8 run.py
```

## 手动安装前端

Windows / macOS / Linux：

```bash
cd frontend
npm install
```

## 手动运行前端

Windows / macOS / Linux：

```bash
cd frontend
npm run dev
```
