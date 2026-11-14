# AGY-RESUME (`agyr`) - Quản lý, Nhận diện Phiên bản, Liên kết Thư mục & Tiếp tục phiên Antigravity CLI

`agyr` là công cụ dòng lệnh & giao diện đồ họa (GUI) hỗ trợ tự động quét **100% lịch sử các phiên làm việc** của **Antigravity CLI (`agy`)**, trích xuất thông tin thông minh (thời gian khởi tạo, ngày cập nhật thực tế gần nhất, **phiên bản tương ứng mới nhất của từng tool/project**, **link tới thư mục chính của dự án**, tên dự án, tiêu đề, Git repository, số lượt tương tác, tóm tắt phản hồi của AI) và hỗ trợ **đổi tên dự án / phiên bản / thư mục**, xem chi tiết câu hỏi cũng như tạo phân nhánh (fork/branch) cuộc trò chuyện mà không ảnh hưởng đến phiên gốc.

---

## 🌟 Các tính năng nổi bật

1. **Nhận diện phiên bản tương ứng mới nhất của từng Tool (`🏷️ Phiên bản`)**:
   - Tự động phát hiện phiên bản phát hành mới nhất của từng dự án từ nhiều nguồn:
     - `package.json` (`version`)
     - `manifest.json` (Chrome Extension `version`)
     - `pyproject.toml` / `setup.py` / `Cargo.toml`
     - `VERSION` / `version.txt` / `version.json`
     - Header plugin WordPress (`* Version: x.y.z`)
     - Lịch sử Git commits (`git log` chứa mẫu `vX.Y.Z` hoặc `release: vX.Y.Z`)
     - Git tags gần nhất (`git describe --tags`)
   - Cho phép người dùng tùy ý chỉnh sửa, đặt lại phiên bản theo ý muốn.

2. **Cột liên kết tới Thư mục chính của Dự án (`📁 Thư mục chính`)**:
   - Hiển thị đường dẫn thư mục gốc nơi dự án được triển khai và phát triển.
   - **Thao tác 1-click**: Double-click trực tiếp vào ô thư mục trên bảng GUI để mở ngay thư mục đó trong **Windows File Explorer**.
   - Hỗ trợ đổi đường dẫn thư mục chính thông qua hộp thoại duyệt thư mục trực quan (`📁 Duyệt...`).

3. **Giao diện bảng điều khiển đồ họa GUI chuyên nghiệp (`-g` / `--gui`)**:
   - Bảng điều khiển cửa sổ trực quan hiển thị đầy đủ các cột: `#`, `📌 Dự án`, `🏷️ Phiên bản`, `📝 Tiêu đề`, `📁 Thư mục chính`, `🕒 Ngày cập nhật`, `Lượt`, `🔗 Git Repo`, `💬 Yêu cầu gần nhất`, `🆔 ID`.
   - Lọc tìm kiếm thời gian thực tức thì theo mọi tiêu chí (tên dự án, phiên bản, tiêu đề, git repo, thư mục, nội dung câu hỏi...).
   - Hỗ trợ sắp xếp cột (Sorting) tăng/giảm chỉ bằng cách click vào tiêu đề cột.
   - Thao tác nhanh bằng chuột hoặc phím tắt:
     - **`Enter`** hoặc **Double-click**: Tiếp tục phiên làm việc trong `agy`.
     - **Double-click cột Thư mục chính**: Mở ngay thư mục dự án trong Windows Explorer.
     - **`F2`**: Mở hộp thoại Đổi tên dự án, Phiên bản, Tiêu đề & Thư mục.
   - Menu chuột phải (Context Menu) với đầy đủ chức năng tiện lợi: mở thư mục, sao chép đường dẫn, sao chép ID, sao chép lệnh `agy --conversation ...`.

4. **Đổi tên dự án, Phiên bản, Tiêu đề & Thư mục (`Rename / Edit`)**:
   - Cho phép bạn tự đặt lại tên dự án (ví dụ: `Colophon Ebook Reader`, `VNPT HIS Extension`...) thay vì các tên mặc định như `Chung (Home)` hay tên thư mục thô.
   - Tự động đồng bộ và cập nhật vĩnh viễn vào cả cơ sở dữ liệu hệ thống `conversation_summaries.db` và cấu hình `custom_project_names.json`.
   - Có thể cập nhật trực tiếp trên GUI (`F2`) hoặc từ terminal (`rn <số>` / `agyr -rn <id>`).

5. **Phân nhánh cuộc trò chuyện (`Branch / Fork`)**:
   - Nhân bản độc lập toàn bộ bộ nhớ, ngữ cảnh, lịch sử câu hỏi - đáp, file scratch và trajectory sang một Conversation ID mới.
   - **Bảo toàn 100% phiên làm việc gốc**: Mọi thay đổi, câu hỏi mới hay thử nghiệm trên nhánh mới hoàn toàn không ảnh hưởng đến phiên gốc.
   - Ghi nhận `Nhánh từ (Parent ID)` để dễ dàng theo dõi nguồn gốc.

6. **Xem chi tiết cuộc trò chuyện & lịch sử câu hỏi (`View Mode`)**:
   - Xem toàn bộ danh sách từng lượt trao đổi (`[LƯỢT 1]`, `[LƯỢT 2]`...): thời gian, câu hỏi người dùng, các công cụ (tools) đã gọi, phản hồi chi tiết của AI và danh sách các file/artifacts sinh ra.

---

## 🚀 Cách sử dụng

Bạn có thể mở bất kỳ cửa sổ dòng lệnh nào (**PowerShell**, **CMD**, **Windows Terminal**) và sử dụng:

### 1. Mở giao diện đồ họa GUI (`-g` / `--gui`)
```powershell
agyr -g
# hoặc:
agyr --gui
```
- Hiển thị bảng điều khiển danh sách toàn bộ các phiên làm việc với đầy đủ cột **Phiên bản** và **Thư mục chính**.
- **Double-click vào cột Thư mục chính**: Mở ngay thư mục dự án trong Windows Explorer.
- **Double-click vào dòng hoặc bấm `Enter`**: Khởi chạy `agy` để tiếp tục phiên làm việc.
- Bấm chọn phiên và nhấn **`F2`** (hoặc nút **`✏️ Đổi tên / Sửa (F2)`**) để chỉnh sửa: Tên dự án, Phiên bản, Tiêu đề và Thư mục chính (có nút Duyệt thư mục).
- Bấm **`📁 Mở thư mục`** để mở thư mục dự án đang chọn trong Windows Explorer.
- Bấm **`🌿 Phân nhánh`** để fork phiên làm việc.
- Bấm **`🔍 Xem chi tiết`** để xem toàn bộ lịch sử hỏi đáp.

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
[1]   14/11/2026 21:54:41 | agy-tools [v2.0.0] (5 lượt)
      📌 Tiêu đề   : Cập Nhật Tính Năng Phiên Bản & Thư Mục
      🏷️ Phiên bản : v2.0.0
      📁 Thư mục   : C:\Users\Admin\Projects\agy-tools
      🔗 Git Repo  : https://github.com/Nsnnam/agy-tools
      🕒 Tạo lúc   : 23/09/2026 11:52:01 | Sửa cuối: 14/11/2026 21:54:41
      🌱 Khởi tạo  : agyr
      💬 Gần nhất  : thêm cột thông tin phiên bản tương ứng mới nhất với từng tool...
      🆔 ID: ea851194-c985-4330-8f9d-bba5583d62f9
----------------------------------------------------------------------
[2]   14/11/2026 21:54:41 | vncare-diachi-web [v1.3.6] (15 lượt)
      📌 Tiêu đề   : Cập Nhật Danh Mục Hành Chính
      🏷️ Phiên bản : v1.3.6
      📁 Thư mục   : C:\Users\Admin\Projects\vncare-diachi-web
      🔗 Git Repo  : https://github.com/Nsnnam/vncare-diachi-web
      ...
----------------------------------------------------------------------

Tuỳ chọn thao tác:
- 1 - 15 hoặc [Enter]    : Tiếp tục phiên [1]
- rn <số> (ví dụ: rn 1)  : ✏️ Đổi tên dự án, phiên bản & tiêu đề
- v <số> (ví dụ: v 1)    : Xem chi tiết câu hỏi & lịch sử phiên
- b <số> (ví dụ: b 1)    : Tạo phân nhánh mới (Branch/Fork)
- <từ khóa>             : Tìm kiếm (tên dự án, phiên bản, tiêu đề, git, nội dung...)
- all                    : Xem toàn bộ phiên làm việc
- g                      : Mở giao diện đồ họa GUI (Session Manager)
- q                      : Thoát

👉 Nhập lựa chọn [Mặc định: 1]: 
```

---

### 3. Đổi tên dự án, phiên bản & thư mục từ dòng lệnh
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
agyr v1.38      # Tìm kiếm các tool đang ở phiên bản v1.38
agyr -l         # Chỉ in danh sách tóm tắt toàn bộ phiên
```
