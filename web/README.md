# AI BI Smart — Web (Next.js)

Giao diện Conversational BI thay Streamlit.

## Chạy

1. Backend FastAPI (thư mục gốc repo):

```bash
uvicorn main:app --reload --port 8000
```

2. Frontend:

```bash
cd web
npm install
npm run dev
```

Mở http://localhost:3000

## Cấu hình

File `.env.local`:

```
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

CORS backend đọc biến `CORS_ORIGINS` (mặc định cho phép localhost:3000).
