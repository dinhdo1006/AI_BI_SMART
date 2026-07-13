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

## Lệnh trên server (sau khi copy file)

```bash
cd ~/Downloads/AI_BI_SMART
source venv/bin/activate   # hoặc .venv

# 1. Copy 4 file từ máy dev (git pull / scp / rsync)

# 2. Tạo lại database mock (BẮT BUỘC — xóa DB cũ)
python seed_db.py

# 3. Restart API + Streamlit
# Ctrl+C các process cũ, rồi:
uvicorn main:app --host 0.0.0.0 --port 2004
python -m streamlit run frontend.py --server.address 0.0.0.0 --server.port 8501
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
INSIGHT_MODEL=qwen2.5:7b
```
