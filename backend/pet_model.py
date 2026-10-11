"""
Mô hình vật lý và máy trạng thái (State Machine) của Desktop Pet.
Vận hành động 100% theo các thông số trong animation.json (dx, dy, durationTicks, onFinish).
"""
import random
from typing import Optional, List
from backend.pet_registry import PetProfile, PetActionConfig, ActionTransition


class PetModel:
    """Mô hình toán học và vật lý của Pet."""

    def __init__(self, profile: PetProfile = None, x: int = 300, y: int = 200, width: int = 128, height: int = 128):
        self.profile = profile
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0

        self.width = width
        self.height = height

        # Giới hạn 4 cạnh màn hình
        self.screen_min_x = 0
        self.screen_max_x = 1920 - self.width
        self.ceiling_y = 0
        self.floor_y = 1080 - self.height

        # Cấu hình vật lý cơ bản
        self.gravity_enabled = True
        self.gravity = 1.2
        self.terminal_velocity = 24.0

        # Trạng thái hành động & hướng
        self.facing_right = True
        self.action = "idle"
        self.active_animation_key = "idle"
        self.ticks_in_state = 0
        self.state_duration = 120

        # Bộ đếm khung hình đồng bộ theo animation.json (dx, dy, durationTicks)
        self.current_frame_idx = 0
        self.frame_tick_count = 0

        # Khởi tạo trạng thái ban đầu
        if self.y < self.floor_y - 2:
            self.set_action("fall" if (self.profile and "fall" in self.profile.actions) else "jump")
        else:
            self.set_action("idle")

    def update_screen_bounds(self, min_x: int, max_x: int, floor_y: int, ceiling_y: int = 0):
        """Cập nhật giới hạn 4 cạnh màn hình."""
        self.screen_min_x = min_x
        self.screen_max_x = max_x - self.width
        self.ceiling_y = ceiling_y
        self.floor_y = floor_y - self.height

    def get_action_config(self, action_name: str) -> Optional[PetActionConfig]:
        """Lấy cấu hình của hành động từ profile."""
        if self.profile and action_name in self.profile.actions:
            return self.profile.actions[action_name]
        return None

    def resolve_active_animation(self, action_name: str) -> str:
        """Tìm animation key khớp theo hướng trái/phải nếu có (ví dụ walk -> walk_right)."""
        if not self.profile:
            return action_name

        suffix = "right" if self.facing_right else "left"

        # 1. Thử <action>_<suffix> (ví dụ walk_right, climb_right, stand_right)
        candidate = f"{action_name}_{suffix}"
        if candidate in self.profile.actions:
            return candidate

        # 2. Thử tiền tố đặc thù (climb_ceiling_right cho hang)
        if action_name == "hang":
            candidate = f"climb_ceiling_{suffix}"
            if candidate in self.profile.actions:
                return candidate

        # 3. Thử stand_<suffix> cho idle nếu không có idle
        if action_name == "idle":
            candidate = f"stand_{suffix}"
            if candidate in self.profile.actions:
                return candidate

        # 4. Trả về action_name nếu có trong profile
        if action_name in self.profile.actions:
            return action_name

        return action_name

    def set_action(self, action_name: str, direction_right: Optional[bool] = None):
        """Chuyển đổi sang hành động mới và nạp các thông số từ animation.json."""
        self.action = action_name
        self.ticks_in_state = 0
        self.current_frame_idx = 0
        self.frame_tick_count = 0

        if "left" in action_name:
            self.facing_right = False
        elif "right" in action_name:
            self.facing_right = True
        elif direction_right is not None:
            self.facing_right = direction_right

        self.active_animation_key = self.resolve_active_animation(action_name)
        act_cfg = self.profile.actions.get(self.active_animation_key) or self.get_action_config(action_name)

        if act_cfg:
            self.state_duration = random.randint(act_cfg.duration[0], act_cfg.duration[1])
        else:
            self.state_duration = random.randint(80, 180)

        if action_name == "walk":
            if direction_right is None:
                self.facing_right = random.choice([True, False])
                self.active_animation_key = self.resolve_active_animation("walk")
        elif action_name == "hang":
            self.y = self.ceiling_y
            if direction_right is None:
                self.facing_right = random.choice([True, False])
                self.active_animation_key = self.resolve_active_animation("hang")
        elif action_name == "climb":
            self.active_animation_key = self.resolve_active_animation("climb")

    def start_climb_wall(self, left_side: bool = True):
        """Bắt đầu trèo tường trái hoặc phải nếu pet hỗ trợ action climb."""
        wall_act = self.profile.get_wall_action() if self.profile else None
        if not wall_act:
            self.set_action("walk", direction_right=left_side)
            return

        self.action = "climb"
        self.facing_right = not left_side
        if left_side:
            self.x = self.screen_min_x
        else:
            self.x = self.screen_max_x

        self.active_animation_key = self.resolve_active_animation("climb")
        act_cfg = self.profile.actions.get(self.active_animation_key) or wall_act
        self.ticks_in_state = 0
        self.current_frame_idx = 0
        self.frame_tick_count = 0
        self.state_duration = random.randint(act_cfg.duration[0], act_cfg.duration[1])

    def set_dragged(self, is_dragged: bool, current_x: float = None, current_y: float = None, throw_vx: float = 0.0, throw_vy: float = 0.0):
        """Xử lý sự kiện kéo thả pet bằng chuột."""
        if is_dragged:
            self.action = "drag"
            self.active_animation_key = self.resolve_active_animation("drag")
            self.vx = 0.0
            self.vy = 0.0
            if current_x is not None and current_y is not None:
                self.x = current_x
                self.y = current_y
        else:
            self.vx = max(-18.0, min(18.0, throw_vx))
            self.vy = max(-22.0, min(22.0, throw_vy))
            has_hang = bool(self.profile and ("hang" in self.profile.actions or "climb_ceiling_left" in self.profile.actions))
            if self.y <= self.ceiling_y + 80 and has_hang:
                self.y = self.ceiling_y
                self.vy = 0.0
                self.set_action("hang")
            elif self.y < self.floor_y - 2:
                if (abs(self.vx) > 6.0 or abs(self.vy) > 6.0) and (self.profile and "fling" in self.profile.actions):
                    self.set_action("fling")
                else:
                    self.set_action("fall" if (self.profile and "fall" in self.profile.actions) else "jump")
            else:
                self.y = self.floor_y
                self.vy = 0.0
                self.set_action("idle")
            self.ticks_in_state = 0
            self.state_duration = random.randint(40, 90)

    def choose_next_ground_action(self):
        """Chọn ngẫu nhiên hành động tiếp theo trên mặt đất dựa theo trọng số (weights)."""
        ground_actions = self.profile.get_ground_actions() if self.profile else []
        if not ground_actions:
            self.set_action("idle")
            return

        weights = [act.weight for act in ground_actions]
        chosen = random.choices(ground_actions, weights=weights, k=1)[0]
        self.set_action(chosen.name)

    def _handle_action_finish(self, act_cfg: Optional[PetActionConfig]):
        """Xử lý khi một chuỗi animation kết thúc (dựa vào onFinish trong animation.json)."""
        if act_cfg and act_cfg.on_finish:
            weights = [max(0.01, float(item.weight)) for item in act_cfg.on_finish]
            chosen = random.choices(act_cfg.on_finish, weights=weights, k=1)[0]
            next_action = chosen.to

            if chosen.set_facing == "LEFT" or "left" in next_action:
                self.facing_right = False
            elif chosen.set_facing == "RIGHT" or "right" in next_action:
                self.facing_right = True
            elif chosen.set_facing == "RANDOM":
                self.facing_right = random.choice([True, False])

            self.set_action(next_action)
        else:
            self.choose_next_ground_action()

    def handle_event(self, event_name: str) -> bool:
        """Xử lý các sự kiện tương tác người dùng (như TAP, DRAG, v.v.) dựa theo events trong animation.json."""
        if not self.profile or not self.profile.events:
            if event_name.upper() == "TAP":
                if self.y < self.floor_y - 10:
                    self.set_action("fall" if "fall" in self.profile.actions else "jump")
                    self.vy = 2.0
                else:
                    self.choose_next_ground_action()
                return True
            return False

        ev_upper = event_name.upper()
        matching_rules = []

        cur_category = "GROUND"
        if self.y <= self.ceiling_y + 10:
            cur_category = "CEILING"
        elif self.x <= self.screen_min_x + 10 or self.x >= self.screen_max_x - 10:
            act_cfg = self.profile.actions.get(self.active_animation_key)
            if act_cfg and act_cfg.category == "wall":
                cur_category = "WALL"
        elif self.y < self.floor_y - 10:
            cur_category = "AIR"

        for rule in self.profile.events:
            if rule.event != ev_upper:
                continue

            # 1. Kiểm tra from_action
            if rule.from_action and rule.from_action not in ("*", ""):
                if rule.from_action not in (self.action, self.active_animation_key):
                    continue

            # 2. Kiểm tra allowed_types (WALL, CEILING, GROUND, AIR)
            if rule.allowed_types:
                if cur_category not in rule.allowed_types:
                    continue

            if rule.choices:
                matching_rules.append(rule)

        if not matching_rules:
            if ev_upper == "TAP":
                if cur_category in ("WALL", "CEILING"):
                    self.set_action("fall" if "fall" in self.profile.actions else "jump")
                    self.vy = 2.0
                    return True
                elif cur_category == "GROUND":
                    self.choose_next_ground_action()
                    return True
            return False

        chosen_rule = random.choice(matching_rules)
        valid_choices = [c for c in chosen_rule.choices if c.to in self.profile.actions]
        if not valid_choices:
            valid_choices = chosen_rule.choices

        weights = [max(0.01, float(c.weight)) for c in valid_choices]
        chosen_choice = random.choices(valid_choices, weights=weights, k=1)[0]

        target_to = chosen_choice.to
        if chosen_choice.set_facing == "LEFT" or "left" in target_to:
            self.facing_right = False
        elif chosen_choice.set_facing == "RIGHT" or "right" in target_to:
            self.facing_right = True
        elif chosen_choice.set_facing == "RANDOM":
            self.facing_right = random.choice([True, False])

        if cur_category in ("WALL", "CEILING") and target_to in ("fall", "jump"):
            self.vy = 2.0

        self.set_action(target_to)
        return True

    def tick(self):
        """Cập nhật 1 bước thời gian cho vật lý và chuyển trạng thái đồng bộ theo dx, dy."""
        self.ticks_in_state += 1

        # Khi đang bị kéo thả chuột
        if self.action == "drag":
            act_cfg = self.profile.actions.get(self.active_animation_key) or self.get_action_config(self.action)
            total_frames = len(act_cfg.images) if act_cfg and act_cfg.images else 1
            dur_ticks = act_cfg.frames_ticks[self.current_frame_idx % total_frames] if (act_cfg and act_cfg.frames_ticks) else 6
            self.frame_tick_count += 1
            if self.frame_tick_count >= max(1, dur_ticks):
                self.frame_tick_count = 0
                self.current_frame_idx = (self.current_frame_idx + 1) % total_frames
            return

        act_cfg = self.profile.actions.get(self.active_animation_key) or self.get_action_config(self.action)
        total_frames = len(act_cfg.images) if act_cfg and act_cfg.images else 1
        f_idx = self.current_frame_idx % total_frames if total_frames > 0 else 0

        # Lấy trực tiếp dx, dy và durationTicks từ animation frame
        frame_dx = act_cfg.frames_dx[f_idx] if (act_cfg and f_idx < len(act_cfg.frames_dx)) else 0
        frame_dy = act_cfg.frames_dy[f_idx] if (act_cfg and f_idx < len(act_cfg.frames_dy)) else 0
        dur_ticks = act_cfg.frames_ticks[f_idx] if (act_cfg and f_idx < len(act_cfg.frames_ticks)) else 6

        cat = act_cfg.category if act_cfg else "ground"
        is_wall = (cat == "wall") or ("climb" in self.action or "descend" in self.action)
        is_ceiling = (cat == "ceiling") or ("hang" in self.action or "ceiling" in self.action)
        is_air = (cat == "air") or (self.action in ("fall", "fling", "jump"))

        # 1. Bám mép leo tường (climb, descend)
        if is_wall and not is_ceiling:
            dy = frame_dy if frame_dy != 0 else (-3.0 if "climb" in self.action else 3.0)
            self.y += dy

            # Chạm trần
            if self.y <= self.ceiling_y:
                self.y = self.ceiling_y
                has_hang = bool(self.profile and ("hang" in self.profile.actions or "climb_ceiling_left" in self.profile.actions))
                if has_hang:
                    dir_right = (self.x <= self.screen_min_x + 10)
                    self.set_action("hang", direction_right=dir_right)
                else:
                    self.set_action("fall" if (self.profile and "fall" in self.profile.actions) else "jump")
                    self.vx = 3.5 if not self.facing_right else -3.5
                    self.vy = 1.0
                return

            # Chạm sàn khi bò xuống
            if "descend" in self.action and self.y >= self.floor_y:
                self.y = self.floor_y
                self.choose_next_ground_action()
                return

            # Failsafe: trèo quá lâu mà không chạm trần
            if self.ticks_in_state >= max(self.state_duration, 400):
                self.set_action("fall" if (self.profile and "fall" in self.profile.actions) else "jump")
                self.vx = 3.5 if not self.facing_right else -3.5
                self.vy = -1.0
                return

        # 2. Bám mép trần (hang, climb_ceiling)
        elif is_ceiling:
            self.y = self.ceiling_y
            dx = frame_dx if frame_dx != 0 else (2.0 if self.facing_right else -2.0)
            self.x += dx

            # Đụng mép trần trái / phải
            if self.x <= self.screen_min_x:
                self.x = self.screen_min_x
                self.facing_right = True
                self.active_animation_key = self.resolve_active_animation(self.action)
            elif self.x >= self.screen_max_x:
                self.x = self.screen_max_x
                self.facing_right = False
                self.active_animation_key = self.resolve_active_animation(self.action)

            if self.ticks_in_state >= self.state_duration:
                self.set_action("fall" if (self.profile and "fall" in self.profile.actions) else "jump")
                self.vx = random.choice([-2.0, 0.0, 2.0])
                self.vy = 2.0
                return

        # 3. Rơi tự do trên không (fall, fling, jump)
        elif is_air:
            if self.gravity_enabled:
                if frame_dy != 0:
                    self.y += frame_dy
                else:
                    self.vy = min(self.terminal_velocity, self.vy + self.gravity)
                    self.y += self.vy

            self.x += frame_dx if frame_dx != 0 else self.vx

            # Chạm trần
            if self.y <= self.ceiling_y:
                self.y = self.ceiling_y
                self.vy = abs(self.vy) * 0.4

            # Chạm tường trái / phải khi đang bay
            if self.x <= self.screen_min_x:
                self.x = self.screen_min_x
                if random.random() < 0.6:
                    self.start_climb_wall(left_side=True)
                    return
                else:
                    self.vx = abs(self.vx) * 0.7
            elif self.x >= self.screen_max_x:
                self.x = self.screen_max_x
                if random.random() < 0.6:
                    self.start_climb_wall(left_side=False)
                    return
                else:
                    self.vx = -abs(self.vx) * 0.7

            # Chạm sàn -> tiếp đất
            if self.y >= self.floor_y:
                self.y = self.floor_y
                self.vy = 0.0
                self.vx = 0.0
                self.choose_next_ground_action()
                return

        # 4. Hành động trên mặt đất (walk, idle, sit, motion_1, motion_2, v.v.)
        else:
            if self.gravity_enabled and self.y < self.floor_y - 2:
                self.set_action("fall" if (self.profile and "fall" in self.profile.actions) else "jump")
                return

            self.y = self.floor_y

            # Di chuyển theo frame_dx
            dx = frame_dx
            if dx == 0 and "walk" in self.action:
                dx = 2.0 if self.facing_right else -2.0
            elif "walk" in self.action and not self.active_animation_key.endswith(("_left", "_right")):
                # Nếu action là generic walk chưa có dấu hướng thì gán dấu theo facing_right
                dx = abs(dx) if self.facing_right else -abs(dx)

            self.x += dx

            # Đụng tường trái
            if self.x <= self.screen_min_x:
                self.x = self.screen_min_x
                if random.random() < 0.55:
                    self.start_climb_wall(left_side=True)
                    return
                else:
                    self.facing_right = True
                    self.active_animation_key = self.resolve_active_animation(self.action)

            # Đụng tường phải
            elif self.x >= self.screen_max_x:
                self.x = self.screen_max_x
                if random.random() < 0.55:
                    self.start_climb_wall(left_side=False)
                    return
                else:
                    self.facing_right = False
                    self.active_animation_key = self.resolve_active_animation(self.action)

        # Tiến khung hình animation (theo durationTicks của frame)
        self.frame_tick_count += 1
        if self.frame_tick_count >= max(1, dur_ticks):
            self.frame_tick_count = 0
            self.current_frame_idx += 1

            # Khi hoàn tất 1 chu kỳ animation
            if self.current_frame_idx >= total_frames:
                self.current_frame_idx = 0

                # Chuyển hành động nếu là ONESHOT hoặc đã hết thời lượng
                if act_cfg and act_cfg.loop == "ONESHOT":
                    self._handle_action_finish(act_cfg)
                elif self.ticks_in_state >= self.state_duration:
                    self._handle_action_finish(act_cfg)

        # Giữ pet luôn nằm trong giới hạn ngang màn hình (trừ lúc trèo tường)
        if not is_wall:
            self.x = max(self.screen_min_x, min(self.screen_max_x, self.x))
