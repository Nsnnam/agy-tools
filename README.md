# AGY-RESUME (`agyr`) - Quản lý, Xem chi tiết, Phân nhánh & Tiếp tục phiên Antigravity CLI

`agyr` là công cụ dòng lệnh hỗ trợ tự động quét toàn bộ lịch sử các phiên làm việc của **Antigravity CLI (`agy`)**, trích xuất thông tin thông minh (thời gian khởi tạo, ngày chỉnh sửa gần nhất, tiêu đề, tên dự án, thư mục làm việc, nội dung yêu cầu, số lượt tương tác, mối quan hệ phân nhánh) và hỗ trợ xem chi tiết câu hỏi cũng như tạo phân nhánh (fork/branch) cuộc trò chuyện mà không ảnh hưởng đến phiên gốc.

---

## 🌟 Các tính năng nổi bật

1. **Hiển thị đầy đủ thông tin thời gian & nội dung**:
   - **Thời gian khởi tạo (`Tạo lúc`)** và **Thời gian chỉnh sửa gần nhất (`Sửa cuối`)**.
   - **Nội dung ban đầu (`🌱 Khởi tạo`)**: Yêu cầu/câu hỏi đầu tiên mở đầu phiên làm việc.
   - **Nội dung gần nhất (`💬 Gần nhất`)**: Chỉ đạo/câu hỏi mới nhất đang xử lý.
   - **Tiêu đề AI (`📌 Tiêu đề`)** được trích xuất từ database tổng quan.
2. **Xem chi tiết cuộc trò chuyện & lịch sử câu hỏi (`View Mode`)**:
   - Xem toàn bộ danh sách từng lượt trao đổi (`[LƯỢT 1]`, `[LƯỢT 2]`...): thời gian, câu hỏi người dùng, các công cụ (tools) đã gọi, tóm tắt câu trả lời của AI và danh sách các file/artifacts sinh ra.
3. **Phân nhánh cuộc trò chuyện (`Branch / Fork`)**:
   - Nhân bản độc lập toàn bộ bộ nhớ, ngữ cảnh, lịch sử câu hỏi - đáp, file scratch và trajectory sang một Conversation ID mới.
   - **Bảo toàn 100% phiên làm việc gốc**: Mọi thay đổi, câu hỏi mới hay thử nghiệm trên nhánh mới hoàn toàn không ảnh hưởng đến phiên gốc.
   - Ghi nhận `Nhánh từ (Parent ID)` để dễ dàng theo dõi nguồn gốc.
4. **Hỗ trợ 2 chế độ chọn**:
   - **Terminal tương tác**: Hỗ trợ phím tắt số, lệnh xem `v <số>`, lệnh phân nhánh `b <số>`, tìm kiếm từ khóa.
   - **Giao diện bảng GUI Windows (`-g` / `--gui`)**: Bảng `Out-GridView` trực quan với bộ lọc tìm kiếm tức thì.

---

## 🚀 Cách sử dụng

Bạn có thể mở bất kỳ cửa sổ dòng lệnh nào (**PowerShell**, **CMD**, **Windows Terminal**) và sử dụng:

### 1. Mở menu tương tác chính
```powershell
agyr
# hoặc:
agy-resume
```
**Giao diện trực quan:**
```text
======================================================================
       ANTIGRAVITY CLI - TIẾP TỤC PHIÊN LÀM VIỆC (AGY-RESUME)         
======================================================================
[1]   17/09/2026 13:51:06 | BrowserSkill (2 lượt)
      📌 Tiêu đề : Integrate Tencent Browser Skill
      🕒 Tạo lúc : 17/09/2026 13:21:21 | Sửa cuối: 17/09/2026 13:51:06
      📁 Thư mục : C:\Users\Admin
      🌱 Khởi tạo: Có cần tích hợp thêm skill trình duyệt này không...
      💬 Gần nhất: lỗi gì đó ko tự động bật lên được
      🆔 ID: fe81b7ce-f058-460d-97e3-2185b1f34942
----------------------------------------------------------------------
[2]   17/09/2026 07:51:57 | vncare-xml-pro-assistant (1 lượt) [Nhánh từ: 3654e57b]
      📌 Tiêu đề : Kiểm tra repository vncare-xml-pro-assistant
      ...
----------------------------------------------------------------------

Tuỳ chọn thao tác:
- 1 - 10 hoặc [Enter]    : Tiếp tục phiên [1]
- v <số> (ví dụ: v 3)    : Xem chi tiết câu hỏi & lịch sử phiên
- b <số> (ví dụ: b 3)    : Tạo phân nhánh mới (Branch/Fork)
- <từ khóa>             : Tìm kiếm theo tên dự án, tiêu đề, nội dung
- g                      : Mở giao diện bảng chọn GUI (Out-GridView)
- q                      : Thoát

👉 Nhập lựa chọn [Mặc định: 1]: 
```

### 2. Xem chi tiết câu hỏi & lịch sử cuộc trò chuyện (`-v` / `--view`)
```powershell
# Xem chi tiết phiên số 3:
agyr -v 3

# Hoặc xem chi tiết theo Conversation ID:
agyr -v fe81b7ce-f058-460d-97e3-2185b1f34942
```
*Sau khi xem xong, bạn có thể chọn:*
- Bấm **`r`**: Tiếp tục phiên này.
- Bấm **`b`**: Tạo phân nhánh mới từ phiên này.
- Bấm **`q`**: Quay lại.

### 3. Tạo phân nhánh cuộc trò chuyện (`-b` / `--branch`)
```powershell
# Tạo phân nhánh từ phiên số 3:
agyr -b 3

# Hoặc tạo phân nhánh theo ID:
agyr -b fe81b7ce-f058-460d-97e3-2185b1f34942
```
- Tool sẽ cho phép bạn đặt tên/ghi chú cho nhánh mới.
- Toàn bộ cơ sở dữ liệu trajectory và thư mục brain được nhân bản độc lập.
- Khởi chạy ngay `agy --conversation <nhánh-mới>` để bạn tiếp tục phát triển hướng đi mới!

### 4. Mở giao diện bảng chọn đồ họa GUI Windows (`-g` / `--gui`)
```powershell
agyr -g
```
- Mở cửa sổ Windows `Out-GridView` gồm các cột: *STT, Tiêu đề, Dự án, Ngày tạo, Ngày cập nhật, Số lượt, Yêu cầu ban đầu, Yêu cầu gần nhất, Nhánh gốc, Thư mục*.
- Gõ tìm kiếm tức thì trên thanh Filter và chọn phiên mong muốn.

### 5. Tiếp tục ngay phiên số 1 hoặc tìm kiếm
```powershell
agyr 1          # Tiếp tục ngay phiên gần nhất
agyr famorg     # Tìm kiếm các phiên liên quan đến FamOrg
agyr -l         # Chỉ in danh sách tóm tắt
```
