# PDS FastAPI 后端

## 一键安装并运行

回到项目根目录运行：

Windows PowerShell：

```powershell
python .\start.py
```

macOS / Linux：

```bash
python3 start.py
```

## 手动安装

Windows PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS / Linux：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 手动运行

Windows PowerShell：

```powershell
.\.venv\python.exe -X utf8 run.py
```

macOS / Linux：

```bash
source .venv/bin/activate
python -X utf8 run.py
```

后端地址：`http://127.0.0.1:8100/`
