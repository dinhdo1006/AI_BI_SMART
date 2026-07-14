# Đồng bộ lên server sau cập nhật

## File thay đổi (copy lên `~/Downloads/AI_BI_SMART`)

| File | Thay đổi |
|------|----------|
| `seed_db.py` | **Viết lại** — mock data phong phú hơn (xem bảng dưới) |
| `core/insight_stats.py` | **File mới** — tính stats trước insight |
| `core/llm_agent.py` | Insight dùng stats + cấu trúc báo cáo 4 phần |
| `core/sql_fast_path.py` | Thêm 7 mã CP (VNM, TCB, BID, GAS, MSN, REE, PNJ) |

## File KHÔNG đổi (giữ nguyên trên server)

- `frontend.py`, `api/routes.py`, `.env`, `main.py`, `configs/*.json`

---

## Dữ liệu mock mới (sau `python seed_db.py`)

| Domain | Trước | Sau |
|--------|-------|-----|
| **Finance** | 5 mã, 40 phiên, 5 BCTC | **12 mã**, **720 phiên** (60/ngày), **60 BCTC** (5 quý) |
| **IT** | 8 dự án, 26 snapshot | **15 dự án**, **~120 snapshot** (hàng tuần 14 tuần) |
| **Mining** | 8 khu, 12 khảo sát | **12 khu**, **~46 khảo sát** (nhiều mốc thời gian) |

### Kịch bản demo có sẵn trong data

- **FPT:** giá tăng dần 3 tuần gần nhất
- **HPG:** khối lượng GD đột biến phiên cuối
- **SAP S/4HANA Pilot:** tiến độ chậm (~42%)
- **BCTC:** Q1/2025 → Q1/2026 có tăng trưởng theo quý

---

## Quy trình deploy chuẩn (đã kiểm chứng 2026-07-13)

### ⚠️ Lưu ý quan trọng về server

| Vấn đề | Chi tiết |
|--------|---------|
| **venv đúng** | Dùng `.venv` trong project, KHÔNG phải `venv` hay `~/Downloads/venv` |
| **Không có pm2** | Dùng `nohup ... &` để chạy background |
| **Không sửa code trực tiếp trên server** | Server chỉ `git pull`, mọi sửa đổi làm trên máy dev rồi push |
| **Conflict khi pull** | Chạy `git checkout -- <file>` hoặc `git reset --hard HEAD` trước khi pull |

### Bước 1 — Máy dev: commit + push

```bash
cd d:\AI_BI_SMART
git add <các file đã sửa>
git commit -m "mô tả thay đổi"
git push origin main
```

### Bước 2 — Server: pull code

```bash
cd ~/Downloads/AI_BI_SMART

# Nếu bị conflict
git reset --hard HEAD

git pull origin main
```

### Bước 3 — Server: restart FastAPI

```bash
cd ~/Downloads/AI_BI_SMART
source .venv/bin/activate   # ← ĐÚNG venv, không dùng venv khác

# Kill process cũ nếu có
pkill -f "uvicorn main:app" 2>/dev/null; sleep 1

# Start lại
nohup uvicorn main:app --host 0.0.0.0 --port 2004 > ~/uvicorn_bi.log 2>&1 &

# Kiểm tra
sleep 3 && curl http://127.0.0.1:2004/health
# Kết quả mong đợi: {"status":"ok","schema_rag_enabled":true}
```

### Bước 4 — Server: rebuild + restart Next.js (chỉ khi có sửa web/)

```bash
cd ~/Downloads/AI_BI_SMART/web
npm install   # chỉ cần nếu package.json thay đổi
npm run build

# Tìm và kill process Next.js cũ
pkill -f "next start" 2>/dev/null; sleep 1

# Start lại
nohup npm run start > ~/nextjs_bi.log 2>&1 &
```

### Kiểm tra log khi có lỗi

```bash
tail -f ~/uvicorn_bi.log   # log FastAPI
tail -f ~/nextjs_bi.log    # log Next.js
```

---

## Câu hỏi test sau cập nhật

**Finance:**
- `Top 10 vốn hóa HoSE`
- `So sánh doanh thu FPT qua các quý từ Q1/2025 đến Q1/2026`
- `FPT giá và khối lượng 20 phiên gần nhất, combo chart`
- `Mã nào tăng mạnh nhất phiên gần nhất`

**IT:**
- `Xu hướng tiến độ FSI theo thời gian, biểu đồ đường`
- `Dự án SAP S/4HANA tiến độ thế nào`
- `Ngân sách lớn nhất top 10`

**Mining:**
- `Trữ lượng theo tỉnh`
- `Diễn biến trữ lượng khảo sát theo thời gian`
- `Hàm lượng cao nhất top 5`

---

## .env trên server (không đổi nếu đã cấu hình)

```env
API_BASE=http://127.0.0.1:2004
SQL_MODEL=sqlcoder:7b
INSIGHT_MODEL=qwen2.5:14b
```
