# AI BI Smart — Web (Next.js)

Giao diện Conversational BI thay Streamlit.

**Port UI mặc định: `3010`**

## Kiến trúc gọi API

Trình duyệt gọi **cùng origin** (`/api/...`). Next.js **rewrite** sang FastAPI
(`BACKEND_URL`, mặc định `http://127.0.0.1:2004`). Không cần CORS, không cần
IP LAN trong `NEXT_PUBLIC_*`.

## Chạy

1. Backend:

```bash
uvicorn main:app --host 0.0.0.0 --port 2004
```

2. Frontend:

```bash
cd web
# .env.local — chỉ cần URL nội bộ server → FastAPI
echo "BACKEND_URL=http://127.0.0.1:2004" > .env.local
# Không set NEXT_PUBLIC_API_BASE (để trống = dùng proxy)

npm install
npm run build
npm run start
```

Mở http://10.10.6.134:3010 (hoặc IP máy bạn).

> **Viết bài báo:** endpoint `/api/v1/generate_article` đi qua Route Handler
> riêng (timeout 5 phút). Sau khi pull code mới cần **restart Next.js**
> (`npm run build && npm run start` hoặc `npm run dev`).

## Cấu hình tùy chọn

| Biến | File | Ý nghĩa |
|------|------|---------|
| `BACKEND_URL` | `web/.env.local` | FastAPI nội bộ cho rewrite (build-time) |
| `NEXT_PUBLIC_API_BASE` | `web/.env.local` | Chỉ khi muốn gọi API trực tiếp, bỏ proxy |
| `CORS_ORIGINS` | `.env` gốc | Chỉ cần nếu dùng `NEXT_PUBLIC_API_BASE` |
