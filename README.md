# AGY-RESUME (`agyr`) - Công cụ tải và tiếp tục các phiên làm việc Antigravity CLI

`agyr` là công cụ dòng lệnh hỗ trợ tự động quét toàn bộ lịch sử các phiên làm việc trước đó của **Antigravity CLI (agy)**, trích xuất thông tin thông minh (thời gian, tên dự án, thư mục làm việc, nội dung yêu cầu, số lượt tương tác) và cho phép bạn chọn nhanh phiên cần tiếp tục.

---

## 🚀 Cách sử dụng

Bạn có thể mở bất kỳ cửa sổ dòng lệnh nào (PowerShell, CMD, Windows Terminal) và gõ:

### 1. Mở menu tương tác
```powershell
agyr
# hoặc
agy-resume
```
- Danh sách 10 phiên làm việc gần nhất sẽ được hiển thị kèm số thứ tự `[1]`, `[2]`, `[3]`...
- Nhấn **`[Enter]`** hoặc gõ **`1`** để tiếp tục ngay phiên gần đây nhất.
- Gõ số thứ tự bất kỳ (ví dụ: `4`) để tiếp tục phiên đó.
- Gõ từ khóa bất kỳ (ví dụ: `famorg`, `excel`, `vang`...) để lọc tìm kiếm.
- Gõ **`g`** để mở bảng chọn GUI trực quan (cửa sổ Windows Out-GridView).
- Gõ **`q`** để thoát.

### 2. Tiếp tục ngay phiên số 1 (gần nhất)
```powershell
agyr 1
```

### 3. Tìm kiếm theo từ khóa
```powershell
agyr famorg
agyr excel
agyr ebook
```

### 4. Mở cửa sổ giao diện GUI (Out-GridView)
```powershell
agyr -g
# hoặc
agyr --gui
```
- Hiển thị bảng chọn có sẵn thanh tìm kiếm của Windows.
- Nhấp chọn phiên mong muốn rồi bấm **OK** để tự động khởi chạy `agy`.

### 5. Chỉ xem danh sách (không vào tương tác)
```powershell
agyr -l
# hoặc
agyr --list
```

---

## 🛠 Cơ chế hoạt động
1. **Tự động quét**: Đọc dữ liệu từ `%USERPROFILE%\.gemini\antigravity-cli\brain`.
2. **Nhận diện thông minh**:
   - Tự nhận diện thư mục làm việc (`Cwd`, đường dẫn `Projects\...`, hoặc URL GitHub).
   - Làm sạch văn bản yêu cầu của người dùng, loại bỏ các thẻ metadata hệ thống.
3. **Tự động chuyển thư mục**: Trước khi khôi phục phiên, tool sẽ tự động `cd` vào thư mục dự án tương ứng để đảm bảo `agy` có đúng ngữ cảnh workspace.
4. **Khởi chạy `agy`**: Chạy lệnh `agy --conversation <id>` tiếp tục liền mạch công việc còn dang dở.
