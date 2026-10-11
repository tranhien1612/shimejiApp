# Shimeji Desktop Pet (Anime Virtual Mascot)

Ứng dụng nuôi thú cưng ảo (Desktop Pet) dạng nhân vật anime tương tác trực tiếp trên màn hình máy tính sử dụng Python và PyQt6.

## Tính năng nổi bật
1. **Hiển thị tự do không giới hạn**: Thú cưng di chuyển trên toàn màn hình với nền trong suốt tuyệt đối (`WA_TranslucentBackground`), không có viền cửa sổ (`FramelessWindowHint`).
2. **Hệ thống tương tác 4 cạnh màn hình phong phú**:
   - **Cạnh đáy (Sàn/Taskbar)**: Đi dạo, bò trườn (`CRAWL_FLOOR`), ngồi nghỉ (`SIT`), nhảy bật lên cao (`JUMP`).
   - **Cạnh trái & Cạnh phải (Tường)**: Bám tường leo trèo (`CLIMB_WALL_LEFT`, `CLIMB_WALL_RIGHT`) lên đến nóc hoặc buông tay bật ra.
   - **Cạnh trên (Trần)**: Bám trần lộn ngược bò ngang (`CRAWL_CEILING`), hoặc buông tay rơi xuống.
   - **Đu dây từ trần (`ROPE_SWING`)**: Thả sợi dây từ mép trên màn hình, đu qua lại theo dao động con lắc mượt mà rồi thả dây rơi xuống sàn.
   - Kéo thả tự do bằng chuột, quăng ném theo gia tốc chuột.
   - Nhấp đúp chuột để pet nhảy bật vui vẻ.
   - Nhấp chuột phải vào pet để kích hoạt ngay lập tức bất kỳ hành động nào trong 4 cạnh.
   - Bảng Quản Lý có nhóm nút "Hiệu ứng 4 cạnh màn hình" để ra lệnh cho toàn bộ pet cùng nhảy, cùng leo tường, bám trần hoặc đu dây.
3. **Cơ chế chạy ngầm System Tray**:
   - Khi đóng cửa sổ cấu hình/quản lý (bấm nút X), ứng dụng không tắt mà tự động thu nhỏ chạy ngầm dưới khay hệ thống (System Tray).
   - Menu chuột phải tại icon khay hệ thống: Mở lại bảng quản lý, Thêm pet, Tập hợp pet, Xóa pet, và nút **Thoát Hoàn Toàn (Exit)**.
   - Ứng dụng chỉ tắt hoàn toàn khi chọn Exit từ khay hệ thống.
4. **Cơ chế nạp Pet hoàn toàn tự động từ thư mục `assets/` (Dynamic Pet Auto-Discovery)**:
   - Ứng dụng tự động quét tất cả các thư mục con trong thư mục `assets/`.
   - Mỗi thư mục con là một nhân vật Pet, tên pet chính là tên thư mục.
   - Hành động và danh sách khung hình tự động đọc và phân giải từ `animation.json` và `manifest.json`.
   - Ảnh đại diện cho pet là file `thumbnail.webp` trong thư mục pet đó.
   - **Thêm Pet mới**: Chỉ cần thả thư mục pet vào `assets/` là ứng dụng tự động nhận diện và hiển thị trong menu, **hoàn toàn không cần sửa code backend**.

## Cấu trúc thư mục

```text
shimejiApp/
├── assets/
│   ├── Roronoa Zoro/               # Thư mục nhân vật Zoro
│   │   ├── sprites/                # %04d.webp
│   │   ├── thumbnail.webp          # Ảnh đại diện
│   │   ├── manifest.json           # Thông tin metadata
│   │   └── animation.json          # Danh sách hành động và frames
│   └── Satoru Gojo/                # Thư mục nhân vật Gojo
│       ├── sprites/                # %04d.webp
│       ├── thumbnail.webp          # Ảnh đại diện
│       ├── manifest.json           # Thông tin metadata
│       └── animation.json          # Danh sách hành động và frames
├── backend/
│   ├── __init__.py
│   ├── pet_model.py                # State machine & vật lý vận hành động
│   ├── pet_registry.py             # Quét tự động thư mục assets/ và nạp Pet
│   └── pet_manager.py              # Điều phối vòng đời và các pet đang hoạt động
├── ui/
│   ├── __init__.py
│   ├── pet_widget.py               # Render động, bộ nhớ đệm SpriteCache, menu ngữ cảnh
│   └── tray_icon.py                # Quản lý khay hệ thống (System Tray)
├── tests/
│   └── test_pet_logic.py           # Bộ kiểm thử tự động
├── main.py                         # File khởi chạy chính
├── requirements.txt
└── README.md
```

## Hướng dẫn cài đặt & Chạy

1. **Cài đặt thư viện**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Khởi chạy ứng dụng**:
   ```bash
   python main.py
   ```

3. **Chạy kiểm thử logic**:
   ```bash
   python tests/test_pet_logic.py
   ```

## Đóng gói thành file .exe

Để đóng gói ứng dụng thành file `.exe` chạy độc lập trên Windows:
```bash
python build.py
```
- File `.exe` sẽ được tạo tại `dist/ShimejiPet.exe` kèm thư mục `dist/assets/`.
- Tùy chọn đóng gói dạng thư mục phân phối (One-Directory):
  ```bash
  python build.py --onedir
  ```
- Dọn dẹp cache build cũ trước khi đóng gói:
  ```bash
  python build.py --clean
  ```
