"""
Bộ điều phối và quản lý toàn bộ các Pet đang hoạt động (Pet Manager).
Vận hành dựa trên danh mục nạp tự động từ thư mục `assets/`.
"""
import random
from typing import List
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from ui.pet_widget import PetWidget
from backend.pet_registry import PetRegistry


class PetManager(QObject):
    """Quản lý vòng đời và cấu hình của các thú cưng trên màn hình."""

    pet_count_changed = pyqtSignal(int)
    default_pet_changed = pyqtSignal(str)

    def __init__(self, assets_dir: str = "assets"):
        super().__init__()
        # Quản lý danh mục pet được quét tự động từ thư mục assets
        self.registry = PetRegistry(assets_dir)
        self.pets: List[PetWidget] = []

        # Cấu hình dùng chung
        self.global_scale = 128
        self.gravity_enabled = True

    def set_default_pet(self, pet_id: str):
        """Đặt pet làm mặc định và thông báo cho UI."""
        if self.registry.set_default_pet(pet_id):
            self.default_pet_changed.emit(pet_id)

    def spawn_pet(self, pet_id: str = None, x: int = None, y: int = None) -> PetWidget:
        """Tạo mới một bé pet xuất hiện trên màn hình từ profile trong config."""
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None

        if x is None:
            min_x = avail.left() + 100 if avail else 100
            max_x = avail.right() - 200 if avail else 800
            x = random.randint(min_x, max(min_x, max_x))
        if y is None:
            min_y = avail.top() + 50 if avail else 50
            max_y = avail.top() + 300 if avail else 300
            y = random.randint(min_y, max_y)

        # Lấy profile tương ứng từ config
        target_id = pet_id or self.registry.default_pet_id
        if target_id == "None":
            return None
        if not target_id:
            if self.registry.profiles:
                target_id = next(iter(self.registry.profiles.keys()))
            else:
                return None

        profile = self.registry.get(target_id)
        if not profile:
            return None

        pet = PetWidget(
            profile=profile,
            initial_x=x,
            initial_y=y,
            scale_size=self.global_scale
        )
        pet.model.gravity_enabled = self.gravity_enabled

        # Kết nối tín hiệu từ pet
        pet.pet_removed.connect(self.remove_pet)
        pet.pet_cloned.connect(self._on_pet_cloned)

        pet.show()
        self.pets.append(pet)
        self.pet_count_changed.emit(len(self.pets))
        return pet

    def _on_pet_cloned(self, source_pet: PetWidget):
        """Nhân bản chính xác loại pet đó."""
        self.spawn_pet(
            pet_id=source_pet.profile.id,
            x=int(source_pet.x() + 40),
            y=int(source_pet.y())
        )

    def remove_pet(self, pet: PetWidget):
        """Xóa 1 pet cụ thể và dọn dẹp bộ nhớ."""
        if pet in self.pets:
            self.pets.remove(pet)
            pet.close()
            pet.deleteLater()
            if not self.pets:
                from ui.pet_widget import SpriteCache
                SpriteCache.clear()
            self.pet_count_changed.emit(len(self.pets))

    def remove_last_pet(self):
        """Xóa bớt 1 pet gần nhất và giải phóng bộ nhớ."""
        if self.pets:
            self.remove_pet(self.pets[-1])

    def remove_all_pets(self):
        """Xóa sạch mọi pet trên màn hình và giải phóng toàn bộ tài nguyên."""
        for pet in list(self.pets):
            pet.close()
            pet.deleteLater()
        self.pets.clear()
        from ui.pet_widget import SpriteCache
        SpriteCache.clear()
        self.pet_count_changed.emit(0)
