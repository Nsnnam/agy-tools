# AGY-RESUME (`agyr`) - Quản lý, Đổi tên, Phân nhánh & Tiếp tục phiên Antigravity CLI

`agyr` là công cụ hỗ trợ tự động quét **100% lịch sử các phiên làm việc** của **Antigravity CLI (`agy`)**, trích xuất thông tin thông minh (thời gian khởi tạo, ngày cập nhật thực tế gần nhất, tên dự án, tiêu đề, Git repository, thư mục làm việc, nội dung yêu cầu, tóm tắt phản hồi trợ lý) và hỗ trợ **đổi tên dự án / tiêu đề**, xem chi tiết câu hỏi cũng như tạo phân nhánh (fork/branch) cuộc trò chuyện mà không ảnh hưởng đến phiên gốc.

---

## 🌟 Các tính năng nổi bật

1. **Giao diện bảng điều khiển đồ họa GUI (`-g` / `--gui`)**:
   - Bảng điều khiển cửa sổ trực quan với đầy đủ danh sách toàn bộ các phiên làm việc.
   - Thanh tìm kiếm lọc thời gian thực tức thì theo mọi tiêu chí (tên dự án, tiêu đề, git repo, thư mục, câu hỏi...).
   - Hỗ trợ sắp xếp cột (Sorting) tăng/giảm chỉ bằng cách click vào tiêu đề cột.
   - Thao tác nhanh bằng chuột hoặc phím tắt (`Enter` để tiếp tục, `F2` để đổi tên, double click để chạy).
   - Menu chuột phải (Context Menu) với đầy đủ chức năng.
2. **Đổi tên dự án & Tiêu đề phiên (`Rename Feature`)**:
   - Cho phép bạn tự đặt lại **Tên dự án (`Dự án`)** (ví dụ: `Colophon Ebook`, `VNPT HIS Extension`...) thay vì các tên mặc định như `Chung (Home)` hay tên thư mục dài ngoằng.
   - Cho phép sửa đổi **Tiêu đề (`Tiêu đề`)** để ghi nhớ mục tiêu của phiên làm việc.
   - Tự động đồng bộ và cập nhật vĩnh viễn vào cả cơ sở dữ liệu hệ thống `conversation_summaries.db` và cấu hình `custom_project_names.json`.
   - Có thể đổi tên trực tiếp trên giao diện GUI (`F2` hoặc nút "✏️ Đổi tên dự án") hoặc từ terminal (`rn <số>` / `agyr -rn <id>`).
3. **Phân nhánh cuộc trò chuyện (`Branch / Fork`)**:
   - Nhân bản độc lập toàn bộ bộ nhớ, ngữ cảnh, lịch sử câu hỏi - đáp, file scratch và trajectory sang một Conversation ID mới.
   - **Bảo toàn 100% phiên làm việc gốc**: Mọi thay đổi, câu hỏi mới hay thử nghiệm trên nhánh mới hoàn toàn không ảnh hưởng đến phiên gốc.
   - Ghi nhận `Nhánh từ (Parent ID)` để dễ dàng theo dõi nguồn gốc.
4. **Xem chi tiết cuộc trò chuyện & lịch sử câu hỏi (`View Mode`)**:
   - Xem toàn bộ danh sách từng lượt trao đổi (`[LƯỢT 1]`, `[LƯỢT 2]`...): thời gian, câu hỏi người dùng, các công cụ (tools) đã gọi, phản hồi chi tiết của AI và danh sách các file/artifacts sinh ra.
5. **Nhận diện thông minh**:
   - Tự động nhận diện Git Repository (`https://github.com/...`) từ các lượt trao đổi.
   - Sắp xếp chuẩn theo thời gian hoạt động thực tế mới nhất (`updated_at`) của file nhật ký.

---

## 🚀 Cách sử dụng

Bạn có thể mở bất kỳ cửa sổ dòng lệnh nào (**PowerShell**, **CMD**, **Windows Terminal**) và sử dụng:

### 1. Mở giao diện đồ họa GUI (`-g` / `--gui`)
```powershell
agyr -g
# hoặc:
agyr --gui
```
- Hiển thị bảng điều khiển danh sách toàn bộ các phiên làm việc.
- Bấm chọn phiên và nhấn **`F2`** (hoặc bấm nút **✏️ Đổi tên dự án**) để nhập tên dự án và tiêu đề mới dễ nhớ.
- **Double-click** hoặc bấm **`Enter`** (nút **🚀 Tiếp tục**) để mở ngay phiên làm việc trong `agy`.
- Bấm **`🌿 Phân nhánh`** để fork phiên làm việc.
- Bấm **`🔍 Xem chi tiết`** để xem toàn bộ lịch sử hỏi đáp.
- Bấm **`📁 Mở thư mục`** để mở thư mục dự án trong Windows Explorer.

---

### 2. Mở menu tương tác trong Terminal
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
[1]   01/10/2026 08:28:43 | Colophon Ebook Reader (4 lượt)
      📌 Tiêu đề : Tối Ưu Hiệu Năng & Convert EPUB
      🔗 Git Repo: https://github.com/Nsnnam/colophon-vn-ebook, https://github.com/trungtypo-png/epub1t
      🕒 Tạo lúc : 03/09/2026 10:44:49 | Sửa cuối: 01/10/2026 08:28:43
      📁 Thư mục : C:\Users\Admin\Projects\colophon-vn-ebook
      🌱 Khởi tạo: nas của tôi chạy trên địa chỉ https://namns.i234.me:5001/...
      💬 Gần nhất: git này https://github.com/trungtypo-png/epub1t có tính năng convert...
      🆔 ID: a8f08f3f-990b-45e3-b250-72bd70bb354b
----------------------------------------------------------------------

Tuỳ chọn thao tác:
- 1 - 15 hoặc [Enter]    : Tiếp tục phiên [1]
- rn <số> (ví dụ: rn 1)  : ✏️ Đổi tên dự án & tiêu đề phiên
- v <số> (ví dụ: v 1)    : Xem chi tiết câu hỏi & lịch sử phiên
- b <số> (ví dụ: b 1)    : Tạo phân nhánh mới (Branch/Fork)
- <từ khóa>             : Tìm kiếm (tên dự án, tiêu đề, git repo, nội dung...)
- all                    : Xem toàn bộ phiên làm việc
- g                      : Mở giao diện đồ họa GUI (Session Manager)
- q                      : Thoát

👉 Nhập lựa chọn [Mặc định: 1]: 
```

---

### 3. Đổi tên dự án từ dòng lệnh
```powershell
# Đổi tên phiên số 3:
agyr -rn 3
# hoặc:
agyr rename 3

# Hoặc đổi tên theo ID cuộc trò chuyện:
agyr -rn a8f08f3f-990b-45e3-b250-72bd70bb354b
```

---

### 4. Xem chi tiết câu hỏi & lịch sử cuộc trò chuyện (`-v` / `--view`)
```powershell
agyr -v 1
agyr -v a8f08f3f-990b-45e3-b250-72bd70bb354b
```

---

### 5. Tạo phân nhánh cuộc trò chuyện (`-b` / `--branch`)
```powershell
agyr -b 1
agyr -b a8f08f3f-990b-45e3-b250-72bd70bb354b
```

---

### 6. Tiếp tục nhanh hoặc tìm kiếm
```powershell
agyr 1          # Tiếp tục ngay phiên gần nhất
agyr colophon   # Tìm kiếm các phiên liên quan đến từ khóa 'colophon'
agyr -l         # Chỉ in danh sách tóm tắt
```
