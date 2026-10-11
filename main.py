"""
Khởi chạy ứng dụng Shimeji Desktop Pet.
Điểm vào chính (Entry point).
"""
import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PyQt6.QtGui import QFont, QIcon

from backend.pet_manager import PetManager
from ui.tray_icon import TrayIcon


def main():
    # Đảm bảo đường dẫn làm việc đúng thư mục dự án hoặc thư mục chứa file .exe
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    if os.path.exists("assets/app_icon.png"):
        app.setWindowIcon(QIcon("assets/app_icon.png"))

    # Giữ ứng dụng chạy ngầm trong System Tray
    app.setQuitOnLastWindowClosed(False)

    # Kiểm tra hỗ trợ khay hệ thống
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            "Lỗi",
            "Hệ thống của bạn không hỗ trợ khay hệ thống (System Tray)."
        )
        sys.exit(1)

    # Kiểm tra thư mục tài nguyên assets
    if not os.path.isdir("assets"):
        QMessageBox.critical(
            None,
            "Lỗi",
            "Không tìm thấy thư mục 'assets' cạnh file chạy!\nVui lòng đảm bảo thư mục 'assets' nằm cùng cấp với file .exe."
        )
        sys.exit(1)

    # 1. Khởi tạo Backend quản lý Pet (tự động nạp động từ thư mục assets)
    pet_manager = PetManager(assets_dir="assets")

    # 2. Khởi tạo Icon khay hệ thống (cấu hình qua chuột phải vào icon tray)
    tray_icon = TrayIcon(pet_manager)
    tray_icon.show()

    # 3. Xuất hiện bé Pet đầu tiên (nếu có pet mặc định khác "None")
    if pet_manager.registry.default_pet_id and pet_manager.registry.default_pet_id != "None":
        pet_manager.spawn_pet()

    # Không hiển thị bất kỳ cửa sổ nào khi khởi động (chỉ có pet trên màn hình và icon khay)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
