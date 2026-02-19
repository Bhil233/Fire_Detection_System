# AI智能火灾检测系统（FastAPI + Vue + Qwen API）

## 1. 项目结构

```text
test_gpt/
  backend/
    main.py
    requirements.txt
    .env.example
  frontend/
    index.html
    package.json
    vite.config.js
    .env.example
    src/
      main.js
      App.vue
```

## 2. 后端启动（FastAPI）

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

复制环境变量：

```bash
copy .env .env
```

在 `.env` 中填入 Qwen API Key：

```env
QWEN_API_KEY=你的Qwen密钥
QWEN_MODEL=qwen-vl-plus
QWEN_BASE_URL=https://dashscope-us.aliyuncs.com/compatible-mode/v1
```

启动后端：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 3. 前端启动（Vue + Vite）

```bash
cd frontend
npm install
```

复制环境变量：

```bash
copy .env .env
```

启动前端：

```bash
npm run dev
```

默认前端地址：`http://127.0.0.1:5173`

## 4. 使用说明

1. 打开前端页面并上传图片。  
2. 点击“开始检测”。  
3. 若检测到火灾，页面会弹窗警告。  
4. 若未检测到火灾，显示文字：`未发生火灾`。

## 5. 说明

- 后端通过 `httpx` 直接调用 Qwen REST API（OpenAI 兼容模式）。
- 未使用任何 Qwen SDK。
- 如果你在中国大陆，可将 `QWEN_BASE_URL` 改为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
