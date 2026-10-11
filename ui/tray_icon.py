"""
Module quản lý icon và menu ở khay hệ thống (System Tray).
- Thêm / bớt pet
- Chọn Pet mặc định xuất hiện đầu tiên khi khởi động (lưu vào assets/default.json)
- Thoát (Exit)
"""
import os
import sys
from collections import Counter
from typing import Dict
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication,
    QWidgetAction, QListWidget, QListWidgetItem, QFrame
)
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtCore import Qt, QSize

if sys.platform == "win32":
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None


class TrayIcon(QSystemTrayIcon):
    """Icon và menu điều khiển gọn nhẹ nằm dưới khay hệ thống."""

    def __init__(self, pet_manager, parent=None):
        super().__init__(parent)
        self.pet_manager = pet_manager
        self.default_items: Dict[str, QListWidgetItem] = {}

        self.init_tray_icon()
        self.setToolTip("Shimeji Desktop Pets")

        self.setup_menu()

        # Lắng nghe thay đổi pet mặc định để cập nhật menu
        self.pet_manager.default_pet_changed.connect(self.on_default_pet_changed)

    def init_tray_icon(self):
        """Khởi tạo biểu tượng cố định cho ứng dụng trên khay hệ thống (không đổi theo pet)."""
        app_icon_path = os.path.join("assets", "app_icon.png")
        if os.path.exists(app_icon_path):
            self.setIcon(QIcon(app_icon_path))
        else:
            default_profile = self.pet_manager.registry.get(self.pet_manager.registry.default_pet_id)
            if default_profile and default_profile.icon and os.path.exists(default_profile.icon):
                self.setIcon(QIcon(default_profile.icon))

    def setup_menu(self):
        """Khởi tạo menu chuột phải ở khay hệ thống với các chức năng được chỉ định."""
        self.menu = QMenu()
        self.menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:disabled {
                color: #6b7280;
            }
            QMenu::item:selected {
                background-color: #e5e7eb;
                color: #000000;
            }
            QMenu::separator {
                height: 1px;
                background: #e5e7eb;
                margin: 4px 8px;
            }
            QListWidget {
                background-color: transparent;
                color: #000000;
                border: none;
                outline: none;
                font-size: 13px;
                padding: 0px;
            }
            QListWidget::item {
                padding: 6px 12px;
                border-radius: 4px;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #e5e7eb;
                color: #000000;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 6px;
                border-radius: 3px;
                margin: 2px 2px 2px 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # 1. Đang có (Header)
        self.act_header = self.menu.addAction("Running: 0 Pet")
        self.act_header.setEnabled(False)
        self.menu.addSeparator()

        # 2. Mặc định (Menu chọn pet mặc định dạng cuộn gọn gàng)
        cur_default = self.pet_manager.registry.default_pet_id
        cur_profile = self.pet_manager.registry.get(cur_default)
        def_name = cur_profile.name if cur_profile else cur_default
        self.default_menu = self.menu.addMenu(f"Default ({def_name})")
        self.default_list = self._setup_scrollable_pet_list(
            parent_menu=self.default_menu,
            on_select=lambda pid: self.pet_manager.set_default_pet(pid),
            is_default=True
        )

        # 3. Thêm Pet (Menu thêm pet dạng cuộn gọn gàng)
        self.add_menu = self.menu.addMenu("Add")
        self.add_list = self._setup_scrollable_pet_list(
            parent_menu=self.add_menu,
            on_select=lambda pid: self.pet_manager.spawn_pet(pid),
            is_default=False
        )

        # 4. Bớt Pet (Menu con cho phép chọn pet đang chạy để xóa)
        self.remove_menu = self.menu.addMenu("Remove")
        self.menu.addSeparator()

        # Tùy chọn khởi động cùng Windows (chỉ khả dụng và hiển thị trên file .exe đã build)
        if getattr(sys, "frozen", False):
            self.act_autostart = self.menu.addAction("Start with Windows")
            self.act_autostart.setCheckable(True)
            self.act_autostart.setChecked(self.is_autostart_enabled())
            self.act_autostart.triggered.connect(self.set_autostart)
            self.menu.addSeparator()
        else:
            self.act_autostart = None

        # 5. Thoát (Exit)
        self.act_exit = self.menu.addAction("Exit")
        self.act_exit.triggered.connect(self.exit_application)

        # Cập nhật trạng thái menu ngay trước khi show (cực nhanh, không rebuild menu chính)
        self.menu.aboutToShow.connect(self.update_menu_state)
        self.setContextMenu(self.menu)

        # Pre-warm: render offscreen 1 lần để raster-cache toàn bộ font/style, mở tức thì 0ms
        self.prewarm_menu()

    def prewarm_menu(self):
        """Khởi tạo và raster-cache offscreen để menu bật tức thì (<15ms)."""
        try:
            self.menu.ensurePolished()
            self.add_menu.ensurePolished()
            self.default_menu.ensurePolished()
            self.remove_menu.ensurePolished()
            dummy_pix = QPixmap(10, 10)
            self.menu.render(dummy_pix)
            self.add_menu.render(dummy_pix)
            self.default_menu.render(dummy_pix)
            self.remove_menu.render(dummy_pix)
        except Exception:
            pass

    def _setup_scrollable_pet_list(self, parent_menu: QMenu, on_select, is_default: bool = False) -> QListWidget:
        """Tạo danh sách pet có thanh cuộn gọn gàng đặt trong submenu."""
        list_widget = QListWidget()
        list_widget.setMouseTracking(True)
        list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_widget.setFixedWidth(190)
        list_widget.setFixedHeight(270)

        if is_default:
            self.default_items.clear()
            cur_default = self.pet_manager.registry.default_pet_id

            # Mục 'None'
            item_none = QListWidgetItem()
            item_none.setData(Qt.ItemDataRole.UserRole, "None")
            item_none.setData(Qt.ItemDataRole.UserRole + 1, "None")
            prefix = "✓   " if cur_default == "None" else "     "
            item_none.setText(prefix + "None")
            list_widget.addItem(item_none)
            self.default_items["None"] = item_none

            # Đường phân cách
            sep_item = QListWidgetItem()
            sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
            sep_item.setSizeHint(QSize(180, 6))
            sep_line = QFrame()
            sep_line.setFrameShape(QFrame.Shape.HLine)
            sep_line.setStyleSheet("background: #e5e7eb; max-height: 1px;")
            list_widget.addItem(sep_item)
            list_widget.setItemWidget(sep_item, sep_line)

            for profile in self.pet_manager.registry.list_all():
                pet_id = profile.id
                pet_name = profile.name
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, pet_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, pet_name)
                prefix = "✓   " if pet_id == cur_default else "     "
                item.setText(prefix + pet_name)
                list_widget.addItem(item)
                self.default_items[pet_id] = item
        else:
            for profile in self.pet_manager.registry.list_all():
                pet_id = profile.id
                pet_name = profile.name
                item = QListWidgetItem(pet_name)
                item.setData(Qt.ItemDataRole.UserRole, pet_id)
                list_widget.addItem(item)

        def on_item_clicked(item):
            pid = item.data(Qt.ItemDataRole.UserRole)
            if pid:
                on_select(pid)
                self.menu.close()

        list_widget.itemClicked.connect(on_item_clicked)

        widget_action = QWidgetAction(parent_menu)
        widget_action.setDefaultWidget(list_widget)
        parent_menu.addAction(widget_action)

        return list_widget

    def on_default_pet_changed(self, pet_id: str):
        """Cập nhật giao diện menu khi pet mặc định được thay đổi (giữ nguyên icon khay)."""
        cur_profile = self.pet_manager.registry.get(pet_id)
        def_name = cur_profile.name if cur_profile else pet_id
        self.default_menu.setTitle(f"Default ({def_name})")

        for pid, item in self.default_items.items():
            name = item.data(Qt.ItemDataRole.UserRole + 1)
            prefix = "✓   " if pid == pet_id else "     "
            item.setText(prefix + name)

    def update_remove_menu(self):
        """Cập nhật danh sách các pet đang chạy vào menu Bớt Pet."""
        self.remove_menu.clear()
        if not self.pet_manager.pets:
            act_none = self.remove_menu.addAction("(No pet running)")
            act_none.setEnabled(False)
            return

        name_counts = Counter(p.pet_name for p in self.pet_manager.pets)
        seen_counts = {}

        for pet in self.pet_manager.pets:
            name = pet.pet_name
            if name_counts[name] > 1:
                seen_counts[name] = seen_counts.get(name, 0) + 1
                display_text = f"{name} (#{seen_counts[name]})"
            else:
                display_text = name

            act = self.remove_menu.addAction(display_text)
            act.triggered.connect(lambda checked=False, target_pet=pet: self.pet_manager.remove_pet(target_pet))

        if len(self.pet_manager.pets) > 1:
            self.remove_menu.addSeparator()
            act_all = self.remove_menu.addAction(f"Remove all ({len(self.pet_manager.pets)} Pets)")
            act_all.triggered.connect(self.pet_manager.remove_all_pets)

    def update_menu_state(self):
        """Chỉ cập nhật text và trạng thái cần thiết cho action có sẵn, không rebuild menu chính."""
        count = len(self.pet_manager.pets)
        self.act_header.setText(f"Running: {count} Pet")
        self.remove_menu.setEnabled(count > 0)
        self.update_remove_menu()
        if self.act_autostart:
            self.act_autostart.setChecked(self.is_autostart_enabled())

        cur_default = self.pet_manager.registry.default_pet_id
        cur_profile = self.pet_manager.registry.get(cur_default)
        def_name = cur_profile.name if cur_profile else cur_default
        self.default_menu.setTitle(f"Default ({def_name})")
        for pid, item in self.default_items.items():
            name = item.data(Qt.ItemDataRole.UserRole + 1)
            prefix = "✓   " if pid == cur_default else "     "
            item.setText(prefix + name)

        if cur_default in self.default_items:
            self.default_list.scrollToItem(self.default_items[cur_default], QListWidget.ScrollHint.EnsureVisible)

    def is_autostart_enabled(self) -> bool:
        """Kiểm tra xem file .exe đã đăng ký chạy cùng Windows trong Registry chưa."""
        if not getattr(sys, "frozen", False) or not winreg:
            return False
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "ShimejiDesktopPet")
                return bool(val)
        except Exception:
            return False

    def set_autostart(self, enable: bool):
        """Bật/tắt khởi động cùng Windows qua Registry HKCU (chỉ áp dụng cho file .exe đã đóng gói)."""
        if not getattr(sys, "frozen", False) or not winreg:
            return
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    cmd = f'"{sys.executable}"'
                    winreg.SetValueEx(key, "ShimejiDesktopPet", 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, "ShimejiDesktopPet")
                    except FileNotFoundError:
                        pass
        except Exception as e:
            print(f"Lỗi thiết lập khởi động cùng Windows: {e}")

    def exit_application(self):
        """Tắt hoàn toàn ứng dụng và tất cả pet."""
        self.hide()
        self.pet_manager.remove_all_pets()
        QApplication.instance().quit()
