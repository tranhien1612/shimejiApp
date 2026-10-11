"""
Module quét tự động và nạp cấu hình các Pet trực tiếp từ thư mục `assets/`.
Mỗi thư mục con trong `assets/` đại diện cho một nhân vật Pet.
Tên pet là tên thư mục.
Hành động và danh sách sprite được phân giải tự động từ animation.json và manifest.json.
Avatar đại diện là thumbnail.webp.
"""
import os
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ActionTransition:
    to: str
    weight: float = 1.0
    set_facing: Optional[str] = None  # "LEFT", "RIGHT", "RANDOM", etc.


@dataclass
class EventChoice:
    to: str
    weight: float = 1.0
    set_facing: Optional[str] = None


@dataclass
class PetEventRule:
    event: str
    from_action: Optional[str] = None
    allowed_types: List[str] = field(default_factory=list)
    choices: List[EventChoice] = field(default_factory=list)


@dataclass
class PetActionConfig:
    name: str
    label: str
    category: str = "ground"  # "ground", "wall", "ceiling", "air"
    weight: float = 10.0
    duration: List[int] = field(default_factory=lambda: [80, 160])
    speed: float = 3.0
    jump_power: float = 14.0
    images: List[str] = field(default_factory=list)
    frames_dx: List[int] = field(default_factory=list)
    frames_dy: List[int] = field(default_factory=list)
    frames_ticks: List[int] = field(default_factory=list)
    loop: str = "LOOP"  # "LOOP", "ONESHOT"
    on_finish: List[ActionTransition] = field(default_factory=list)


@dataclass
class PetProfile:
    id: str
    name: str
    description: str = ""
    icon: str = ""
    scale_size: int = 128
    walk_speed: float = 3.0
    base_facing: str = "left"
    special_abilities: Dict[str, bool] = field(default_factory=dict)
    actions: Dict[str, PetActionConfig] = field(default_factory=dict)
    events: List[PetEventRule] = field(default_factory=list)

    def get_ground_actions(self) -> List[PetActionConfig]:
        """Lọc danh sách các hành động có thể thực hiện trên mặt đất."""
        return [act for act in self.actions.values() if act.category == "ground" and act.weight > 0]

    def get_wall_action(self) -> Optional[PetActionConfig]:
        """Tìm hành động leo tường nếu pet hỗ trợ."""
        return self.actions.get("climb") or next((a for a in self.actions.values() if a.category == "wall"), None)

    def get_ceiling_actions(self) -> List[PetActionConfig]:
        """Tìm các hành động trên trần (bò trần, đu dây)."""
        return [act for act in self.actions.values() if act.category == "ceiling"]


LABEL_ICON_MAP = {
    "idle": "Đứng thư giãn (Idle)",
    "stand": "Đứng (Stand)",
    "walk": "Bước đi (Walk)",
    "bounce": "Nhún nhảy (Bounce)",
    "jump": "Nhảy cao (Jump)",
    "fall": "Rơi tiếp đất (Fall)",
    "climb": "Bám tường leo lên (Climb)",
    "descend": "Bò tường xuống (Descend)",
    "hang": "Đu bám trần (Hang)",
    "drag": "Bị nhấc bổng (Drag)",
    "fling": "Bị ném văng (Fling)",
    "sit": "Ngồi nghỉ (Sit)",
    "wink": "Nháy mắt (Wink)",
    "creep": "Bò rón rén (Creep)",
    "sprawl": "Nằm duỗi người (Sprawl)",
    "tripping": "Vấp ngã (Tripping)",
    "motion_1": "Chiêu thức 1 (Motion 1)",
    "motion_2": "Chiêu thức 2 (Motion 2)",
    "motion_3": "Chiêu thức 3 (Motion 3)",
    "dance": "Nhảy múa (Dance)",
    "sleep": "Ngủ say (Sleep)",
}


def _make_label(key: str) -> str:
    for prefix, label in LABEL_ICON_MAP.items():
        if key == prefix or key.startswith(prefix + "_") or key.endswith("_" + prefix):
            if "left" in key and "Trái" not in label:
                return f"{label} [Trái]"
            elif "right" in key and "Phải" not in label:
                return f"{label} [Phải]"
            return label
    return key.replace("_", " ").title()


def _alias_if_missing(actions: Dict[str, PetActionConfig], std_name: str, candidates: List[str]):
    """Thiết lập alias hành động chuẩn nếu còn thiếu."""
    if std_name not in actions:
        for c in candidates:
            if c in actions:
                source = actions[c]
                actions[std_name] = PetActionConfig(
                    name=std_name,
                    label=_make_label(std_name),
                    category=source.category,
                    weight=source.weight,
                    duration=list(source.duration),
                    speed=source.speed,
                    jump_power=source.jump_power,
                    images=list(source.images),
                    frames_dx=list(source.frames_dx),
                    frames_dy=list(source.frames_dy),
                    frames_ticks=list(source.frames_ticks),
                    loop=source.loop,
                    on_finish=list(source.on_finish)
                )
                break


class PetRegistry:
    """Quản lý quét thư mục `assets/` và tự động nạp toàn bộ Pet."""

    def __init__(self, assets_dir: str = "assets", config_path: str = "assets/default.json"):
        self.assets_dir = assets_dir
        self.config_path = config_path
        self.default_pet_id = ""
        self.profiles: Dict[str, PetProfile] = {}
        self.reload()

    def _load_saved_default_pet(self) -> str:
        """Đọc id của pet mặc định từ file assets/default.json."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("default_pet", "")
            except Exception as e:
                print(f"Lỗi đọc config: {e}")
        return ""

    def set_default_pet(self, pet_id: str) -> bool:
        """Đặt pet làm mặc định (hỗ trợ 'None' để không hiện pet khi khởi động) và lưu vào file config."""
        if pet_id in self.profiles or pet_id == "None":
            self.default_pet_id = pet_id
            dir_name = os.path.dirname(self.config_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump({"default_pet": pet_id}, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                print(f"Lỗi lưu default pet: {e}")
        return False

    def reload(self):
        """Quét toàn bộ thư mục con trong `assets/` để nhận diện Pet."""
        self.profiles.clear()
        if not os.path.isdir(self.assets_dir):
            print(f"Cảnh báo: Không tìm thấy thư mục {self.assets_dir}")
            return

        for entry_name in sorted(os.listdir(self.assets_dir)):
            pet_dir = os.path.join(self.assets_dir, entry_name)
            if not os.path.isdir(pet_dir):
                continue

            profile = self._load_pet_from_dir(entry_name, pet_dir)
            if profile:
                self.profiles[entry_name] = profile

        saved_default = self._load_saved_default_pet()
        if saved_default == "None":
            self.default_pet_id = "None"
        elif saved_default and saved_default in self.profiles:
            self.default_pet_id = saved_default
        elif self.profiles:
            self.default_pet_id = next(iter(self.profiles.keys()))

    def _load_pet_from_dir(self, pet_name: str, pet_dir: str) -> Optional[PetProfile]:
        manifest_path = os.path.join(pet_dir, "manifest.json")
        anim_path = os.path.join(pet_dir, "animation.json")

        if not os.path.exists(anim_path):
            return None

        # Đọc manifest nếu có
        manifest_data = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception as e:
                print(f"Lỗi đọc manifest tại {manifest_path}: {e}")

        description = manifest_data.get("description", "")
        sprites_cfg = manifest_data.get("sprites", {})
        base_path = sprites_cfg.get("basePath", "sprites/")
        file_pattern = sprites_cfg.get("filePattern", "%04d.webp")
        scale_size = 128

        # Thumbnail
        thumb_name = manifest_data.get("preview", {}).get("thumbnail", "thumbnail.webp")
        icon_path = os.path.normpath(os.path.join(pet_dir, thumb_name)).replace("\\", "/")
        if not os.path.exists(icon_path):
            fallback_thumb = os.path.normpath(os.path.join(pet_dir, "thumbnail.webp")).replace("\\", "/")
            if os.path.exists(fallback_thumb):
                icon_path = fallback_thumb

        # Đọc animation.json
        try:
            with open(anim_path, "r", encoding="utf-8") as f:
                anim_data = json.load(f)
        except Exception as e:
            print(f"Lỗi đọc animation tại {anim_path}: {e}")
            return None

        actions: Dict[str, PetActionConfig] = {}
        for a in anim_data.get("animations", []):
            key = a.get("key")
            if not key:
                continue

            atype = str(a.get("type", "GROUND")).upper()
            subtype = str(a.get("subtype", "")).upper()
            frames = a.get("frames", [])

            loop = str(a.get("loop", "LOOP")).upper()
            on_finish_raw = a.get("auto", {}).get("onFinish", [])
            on_finish = []
            for t in on_finish_raw:
                target_to = t.get("to")
                if target_to:
                    on_finish.append(ActionTransition(
                        to=target_to,
                        weight=float(t.get("weight", 1.0)),
                        set_facing=t.get("setFacing")
                    ))

            images = []
            frames_dx = []
            frames_dy = []
            frames_ticks = []
            for fr in frames:
                s_idx = fr.get("sprite", 0)
                fname = file_pattern % s_idx
                fpath = os.path.normpath(os.path.join(pet_dir, base_path, fname)).replace("\\", "/")
                images.append(fpath)
                frames_dx.append(int(fr.get("dx", 0)))
                frames_dy.append(int(fr.get("dy", 0)))
                frames_ticks.append(int(fr.get("durationTicks", 6)))

            if atype == "GROUND" or (atype == "USER" and subtype == "IDLE"):
                cat = "ground"
            elif atype == "WALL":
                cat = "wall"
            elif atype == "CEILING":
                cat = "ceiling"
            elif atype == "AIR" or subtype in ("DRAG", "FLING"):
                cat = "air"
            else:
                cat = "ground"

            if subtype in ("DRAG", "FLING"):
                weight = 0.0
            elif "walk" in key:
                weight = 30.0
            elif "idle" in key or "stand" in key:
                weight = 25.0
            elif cat in ("wall", "ceiling"):
                weight = 10.0
            elif cat == "air":
                weight = 10.0
            else:
                weight = 15.0

            speed = 3.0
            if cat == "ceiling":
                speed = 2.0
            jump_power = 14.0

            auto_dur = a.get("auto", {}).get("maxDurationTicks")
            if isinstance(auto_dur, dict) and "minTicks" in auto_dur and "maxTicks" in auto_dur:
                duration = [int(auto_dur["minTicks"]), int(auto_dur["maxTicks"])]
            elif isinstance(auto_dur, (int, float)):
                duration = [int(auto_dur), int(auto_dur)]
            elif loop == "ONESHOT":
                total_t = sum(frames_ticks) if frames_ticks else 120
                duration = [total_t, total_t]
            else:
                duration = [120, 240]

            actions[key] = PetActionConfig(
                name=key,
                label=_make_label(key),
                category=cat,
                weight=weight,
                duration=duration,
                speed=speed,
                jump_power=jump_power,
                images=images,
                frames_dx=frames_dx,
                frames_dy=frames_dy,
                frames_ticks=frames_ticks,
                loop=loop,
                on_finish=on_finish
            )

        # Đọc danh sách events tương tác từ animation.json (như TAP, DRAG_START, FLING_START)
        events: List[PetEventRule] = []
        for ev in anim_data.get("events", []):
            ev_name = ev.get("event")
            if not ev_name:
                continue
            choices = []
            for c in ev.get("choices", []):
                target_to = c.get("to")
                if target_to:
                    choices.append(EventChoice(
                        to=target_to,
                        weight=float(c.get("weight", 1.0)),
                        set_facing=c.get("setFacing")
                    ))
            if choices:
                events.append(PetEventRule(
                    event=str(ev_name).upper(),
                    from_action=ev.get("from"),
                    allowed_types=[str(t).upper() for t in ev.get("allowedTypes", [])],
                    choices=choices
                ))

        # Thiết lập các aliases chuẩn
        _alias_if_missing(actions, "idle", ["stand", "stand_left", "stand_right", "sit", "sit_left", "sit_right"])
        _alias_if_missing(actions, "walk", ["walk_left", "walk_right", "run_left", "run_right", "dash_left", "dash_right"])
        _alias_if_missing(actions, "jump", ["bounce", "bounce_left", "bounce_right", "jumping", "jump_left", "jump_up_left", "jump_right"])
        _alias_if_missing(actions, "bounce", ["bounce_left", "bounce_right", "jumping", "jump"])
        _alias_if_missing(actions, "climb", ["climb_left", "climb_right", "climb_wall_left", "climb_wall_right", "grab_wall_left", "grab_wall_right"])
        _alias_if_missing(actions, "descend", ["descend_left", "descend_right", "climb_wall_descend_left", "climb_wall_descend_right"])
        _alias_if_missing(actions, "hang", ["climb_ceiling_left", "climb_ceiling_right", "grab_ceiling_left", "grab_ceiling_right"])
        _alias_if_missing(actions, "fall", ["fall_left", "fall_right", "falling2"])
        _alias_if_missing(actions, "drag", ["fling", "pinched"])

        # Fallback theo category nếu vẫn còn thiếu core actions
        if "climb" not in actions:
            wall_act = next((a for a in actions.values() if a.category == "wall"), None)
            if wall_act:
                _alias_if_missing(actions, "climb", [wall_act.name])
        if "hang" not in actions:
            ceil_act = next((a for a in actions.values() if a.category == "ceiling"), None)
            if ceil_act:
                _alias_if_missing(actions, "hang", [ceil_act.name])

        return PetProfile(
            id=pet_name,
            name=pet_name,
            description=description,
            icon=icon_path,
            scale_size=scale_size,
            walk_speed=3.0,
            base_facing="left",
            special_abilities={},
            actions=actions,
            events=events
        )

    def get(self, pet_id: str) -> Optional[PetProfile]:
        if not pet_id or pet_id == "None":
            return None
        return self.profiles.get(pet_id) or (self.profiles.get(self.default_pet_id) if (self.default_pet_id and self.default_pet_id != "None") else None)

    def list_all(self) -> List[PetProfile]:
        return list(self.profiles.values())
