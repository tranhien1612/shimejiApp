"""
Widget hiển thị Desktop Pet trên màn hình.
Vận hành tối ưu hóa cao:
- Dùng SpriteCache tập trung: tải & scale & pre-flip 1 lần duy nhất trong RAM, chia sẻ chung cho mọi Pet.
- Không cấp phát (0 allocation) QPixmap trong paintEvent -> loại bỏ hoàn toàn giật lag và rò rỉ RAM.
- Gộp timer vật lý & animation vào 1 vòng lặp duy nhất (30 FPS đồng bộ).
- Chỉ gọi move() khi tọa độ thay đổi để giảm tải DWM / Windows event queue.
- Giải phóng triệt để bộ nhớ khi đóng (WA_DeleteOnClose + timer.stop).
"""
import os
import time
from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPainter, QPixmap, QTransform, QColor
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, pyqtSignal

from backend.pet_model import PetModel
from backend.pet_registry import PetProfile


class LazyActionSprites:
    """Bộ nạp frame theo yêu cầu (Lazy On-Demand Loader).
    Chỉ nạp và scale ảnh của hành động khi hành động đó thực sự được kích hoạt.
    Giúp tạo pet mới xuất hiện trên màn hình tức thì (<20ms) thay vì phải đợi nạp hàng trăm ảnh mất 1-2s."""

    def __init__(self, profile: PetProfile, scale_size: int, pixmap_cache: Dict[Tuple[str, int], Optional[Tuple[QPixmap, QPixmap]]]):
        self.profile = profile
        self.scale_size = scale_size
        self.pixmap_cache = pixmap_cache
        self._action_frames: Dict[str, List[Tuple[QPixmap, QPixmap]]] = {}

    def get(self, act_name: str, default=None) -> List[Tuple[QPixmap, QPixmap]]:
        if act_name in self._action_frames:
            return self._action_frames[act_name]

        act_cfg = self.profile.actions.get(act_name)
        if not act_cfg:
            if act_name != "idle":
                return self.get("idle", default)
            return default if default is not None else []

        frames: List[Tuple[QPixmap, QPixmap]] = []
        for img_path in act_cfg.images:
            pix_key = (img_path, self.scale_size)
            if pix_key not in self.pixmap_cache:
                if os.path.exists(img_path):
                    orig = QPixmap(img_path)
                    if not orig.isNull():
                        scaled = orig.scaled(
                            self.scale_size,
                            self.scale_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        flipped = scaled.transformed(
                            QTransform().scale(-1, 1),
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.pixmap_cache[pix_key] = (scaled, flipped)
                    else:
                        self.pixmap_cache[pix_key] = None
                else:
                    self.pixmap_cache[pix_key] = None

            pair = self.pixmap_cache.get(pix_key)
            if pair:
                frames.append(pair)

        if not frames and act_name != "idle":
            frames = self.get("idle", default)

        self._action_frames[act_name] = frames
        return frames

    def __getitem__(self, act_name: str):
        res = self.get(act_name)
        if res is None:
            raise KeyError(act_name)
        return res

    def __contains__(self, act_name: str):
        return act_name in self.profile.actions


class SpriteCache:
    """Bộ nhớ đệm dùng chung:
    - Lưu các cặp QPixmap (normal, flipped) đã scale sẵn.
    - Chia sẻ chung cho mọi PetWidget.
    - Nạp lười (Lazy On-demand): Chỉ nạp frame của hành động đang chạy, tạo pet mới tức thì."""
    _pixmap_cache: Dict[Tuple[str, int], Optional[Tuple[QPixmap, QPixmap]]] = {}
    _action_cache: Dict[Tuple[str, int], LazyActionSprites] = {}

    @classmethod
    def get_action_sprites(cls, profile: PetProfile, scale_size: int) -> LazyActionSprites:
        cache_key = (profile.id, scale_size)
        if cache_key not in cls._action_cache:
            cls._action_cache[cache_key] = LazyActionSprites(profile, scale_size, cls._pixmap_cache)
        return cls._action_cache[cache_key]

    @classmethod
    def clear(cls):
        cls._pixmap_cache.clear()
        cls._action_cache.clear()


class PetWidget(QWidget):
    """Cửa sổ hiển thị một Desktop Pet với hiệu năng tối ưu."""

    pet_removed = pyqtSignal(object)
    pet_cloned = pyqtSignal(object)

    def __init__(self, profile: PetProfile, initial_x: int = 300, initial_y: int = 200, scale_size: int = None, parent=None):
        super().__init__(parent)

        self.profile = profile
        self.scale_size = scale_size or profile.scale_size
        self.pet_name = profile.name

        # Cấu hình cửa sổ trong suốt và không viền
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Mô hình vật lý
        self.model = PetModel(profile=self.profile, x=initial_x, y=initial_y, width=self.scale_size, height=self.scale_size)
        self.resize(self.scale_size, self.scale_size)
        self.move(int(self.model.x), int(self.model.y))

        # Tải hình ảnh từ SpriteCache dùng chung (0 cấp phát lặp lại)
        self.sprites: Dict[str, List[Tuple[QPixmap, QPixmap]]] = {}
        self.load_sprites_from_config()

        # Quản lý kéo thả chuột & tính lực ném
        self.is_mouse_down = False
        self.drag_offset = QPoint(0, 0)
        self.last_mouse_pos = QPoint(0, 0)
        self.last_mouse_time = time.time()
        self.mouse_velocity = (0.0, 0.0)
        self._last_frame_state = None

        # Cập nhật giới hạn màn hình
        self.update_screen_geometry()

        # 1 Timer duy nhất hợp nhất vật lý (~30 FPS) và animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(33)

    def load_sprites_from_config(self):
        """Lấy danh sách sprite (normal, flipped) đã scale từ SpriteCache dùng chung."""
        self.sprites = SpriteCache.get_action_sprites(self.profile, self.scale_size)

    def set_scale_size(self, new_size: int):
        """Thay đổi kích cỡ của pet."""
        self.scale_size = max(64, min(256, new_size))
        self.model.width = self.scale_size
        self.model.height = self.scale_size
        self.resize(self.scale_size, self.scale_size)
        self.load_sprites_from_config()
        self.update_screen_geometry()
        self.update()

    def update_screen_geometry(self):
        """Cập nhật kích thước vùng làm việc màn hình."""
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            self.model.update_screen_bounds(
                avail.left(),
                avail.left() + avail.width(),
                avail.top() + avail.height(),
                avail.top()
            )

    def on_tick(self):
        """Cập nhật vật lý và khung hình đồng bộ trong một nhịp duy nhất."""
        self.model.tick()

        # Chỉ di chuyển và render khi có sự thay đổi tọa độ hoặc khung hình
        nx = int(self.model.x)
        ny = int(self.model.y)
        pos_changed = (nx != self.x() or ny != self.y())
        if pos_changed:
            self.move(nx, ny)

        frame_state = (self.model.active_animation_key, self.model.current_frame_idx, self.model.facing_right)
        if pos_changed or frame_state != self._last_frame_state:
            self._last_frame_state = frame_state
            self.update()

    def get_current_pixmap(self) -> Optional[QPixmap]:
        """Lấy pixmap thích hợp (normal hoặc flipped) với 0 phép phân bổ bộ nhớ mới."""
        action_key = getattr(self.model, "active_animation_key", self.model.action)
        frames = self.sprites.get(action_key) or self.sprites.get(self.model.action) or self.sprites.get("idle", [])
        if not frames:
            return None

        idx = self.model.current_frame_idx % len(frames)
        normal_pix, flipped_pix = frames[idx]

        # Xác định hướng lật theo profile.base_facing
        base_facing = getattr(self.profile, "base_facing", "left")

        facing_right = self.model.facing_right
        if action_key.endswith("_right"):
            facing_right = True
        elif action_key.endswith("_left"):
            facing_right = False

        if base_facing == "left":
            if self.model.action == "climb":
                is_flipped = facing_right
            else:
                is_flipped = facing_right if (self.model.action != "drag") else False
        else:
            if self.model.action == "climb":
                is_flipped = not facing_right
            else:
                is_flipped = (not facing_right) if (self.model.action != "drag") else False

        return flipped_pix if is_flipped else normal_pix

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pix = self.get_current_pixmap()
        if not pix or pix.isNull():
            painter.end()
            return

        x_offset = (self.width() - pix.width()) // 2
        y_offset = (self.height() - pix.height()) // 2

        # Bóng tiếp xúc 3D mềm mại dưới chân nhân vật (Ambient Occlusion Shadow)
        if self.model.action != "climb":
            altitude = max(0.0, self.model.floor_y - self.model.y)
            if altitude < 140:
                sh_alpha = int(max(0, 80 * (1.0 - altitude / 140.0)))
                sh_cx = self.width() / 2.0
                sh_cy = self.height() - 10.0
                sh_rx = (self.scale_size * 0.28) * max(0.4, 1.0 - altitude / 200.0)
                sh_ry = (self.scale_size * 0.08) * max(0.4, 1.0 - altitude / 200.0)

                painter.setBrush(QColor(0, 0, 0, sh_alpha))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(sh_cx, sh_cy), sh_rx, sh_ry)

        # Vẽ hình ảnh trực tiếp từ bộ nhớ đệm (0 transformation cost)
        painter.drawPixmap(x_offset, y_offset, pix)
        painter.end()

    # --- Mouse Events ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_mouse_down = True
            self.drag_offset = event.position().toPoint()
            self.last_mouse_pos = event.globalPosition().toPoint()
            self.press_start_pos = event.globalPosition().toPoint()
            self.press_start_time = time.time()
            self.has_dragged = False
            self.last_mouse_time = time.time()
            self.mouse_velocity = (0.0, 0.0)

            self.model.set_dragged(True, self.x(), self.y())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_mouse_down:
            current_global = event.globalPosition().toPoint()
            if (current_global - self.press_start_pos).manhattanLength() > 6:
                self.has_dragged = True

            now = time.time()
            dt = max(0.001, now - self.last_mouse_time)

            dx = current_global.x() - self.last_mouse_pos.x()
            dy = current_global.y() - self.last_mouse_pos.y()
            vx = (dx / dt) * 0.03
            vy = (dy / dt) * 0.03
            self.mouse_velocity = (vx, vy)

            new_x = current_global.x() - self.drag_offset.x()
            new_y = current_global.y() - self.drag_offset.y()

            self.model.set_dragged(True, new_x, new_y)
            self.move(new_x, new_y)

            self.last_mouse_pos = current_global
            self.last_mouse_time = now

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_mouse_down:
            self.is_mouse_down = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

            # Nếu chỉ là cú click chuột nhẹ (Tap) không kéo thả
            if not self.has_dragged and (time.time() - self.press_start_time < 0.4):
                self.model.set_dragged(False, throw_vx=0.0, throw_vy=0.0)
                self.model.handle_event("TAP")
            else:
                vx, vy = self.mouse_velocity
                self.model.set_dragged(False, throw_vx=vx, throw_vy=vy)
            self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if "jump" in self.profile.actions:
                self.model.set_action("jump")
            else:
                self.model.choose_next_ground_action()
            self.update()

    def closeEvent(self, event):
        """Dọn dẹp triệt để timer và bộ nhớ khi pet bị đóng."""
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        self.sprites = {}
        super().closeEvent(event)
