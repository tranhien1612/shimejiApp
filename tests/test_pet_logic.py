"""
Runnable self-check for dynamic assets-driven PetModel and PetRegistry.
Run: python tests/test_pet_logic.py
"""
import sys
import os

# Add parent dir to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.pet_registry import PetRegistry
from backend.pet_model import PetModel


def test_dynamic_registry_loading():
    registry = PetRegistry("assets")
    profiles = registry.list_all()
    pet_names = [p.name for p in profiles]
    print(f"Loaded {len(profiles)} pets from assets: {pet_names}")
    assert len(profiles) >= 2, f"Expected at least 2 pets, found {len(profiles)}"
    assert "Roronoa Zoro" in pet_names
    assert "Satoru Gojo" in pet_names

    for profile in profiles:
        assert os.path.exists(profile.icon), f"Missing icon for {profile.name}: {profile.icon}"
        # Standard core actions must be present or aliased
        for core_act in ["idle", "walk", "jump", "climb", "hang"]:
            assert core_act in profile.actions, f"Missing core action '{core_act}' in {profile.name}"
            act = profile.actions[core_act]
            assert len(act.images) > 0, f"Action '{core_act}' in {profile.name} has no images"
            for img in act.images:
                assert os.path.exists(img), f"Missing sprite image for {profile.name}: {img}"

    print("[PASS] test_dynamic_registry_loading")


def test_pet_physics_and_fall():
    registry = PetRegistry("assets")
    for profile in registry.list_all():
        model = PetModel(profile=profile, x=100, y=0, width=128, height=128)
        model.update_screen_bounds(min_x=0, max_x=1920, floor_y=1080, ceiling_y=0)

        assert model.action in ("jump", "fall")
        for _ in range(120):
            model.tick()
            if model.y >= model.floor_y:
                break

        assert model.y == model.floor_y
        assert model.action in profile.actions

    print("[PASS] test_pet_physics_and_fall")


def test_climb_and_ceiling():
    registry = PetRegistry("assets")
    for profile in registry.list_all():
        model = PetModel(profile=profile, x=0, y=100, width=128, height=128)
        model.update_screen_bounds(min_x=0, max_x=1920, floor_y=1080, ceiling_y=0)
        model.start_climb_wall(left_side=True)
        assert model.action == "climb"

        for _ in range(80):
            model.tick()
            if model.action != "climb":
                break

        assert model.action == "hang"
        assert model.y == model.ceiling_y

        init_x = model.x
        for _ in range(10):
            model.tick()
        assert model.x != init_x
        assert model.y == model.ceiling_y

        model.ticks_in_state = model.state_duration
        model.tick()
        assert model.action in ("jump", "fall")

    print("[PASS] test_climb_and_ceiling")


def test_drag_and_drop():
    registry = PetRegistry("assets")
    for profile in registry.list_all():
        model = PetModel(profile=profile, x=200, y=952, width=128, height=128)
        model.update_screen_bounds(min_x=0, max_x=1920, floor_y=1080, ceiling_y=0)

        model.set_dragged(True, current_x=300, current_y=200)
        assert model.action == "drag"
        assert model.x == 300

        model.set_dragged(False, throw_vx=5.0, throw_vy=-10.0)
        assert model.action in ("jump", "fall", "fling")
        assert model.vx == 5.0

    print("[PASS] test_drag_and_drop")


def test_walk_movement_dx_dy():
    registry = PetRegistry("assets")
    for profile in registry.list_all():
        model = PetModel(profile=profile, x=500, y=952, width=128, height=128)
        model.update_screen_bounds(min_x=0, max_x=1920, floor_y=1080, ceiling_y=0)

        # Test walk right
        model.set_action("walk_right" if "walk_right" in profile.actions else "walk", direction_right=True)
        start_x = model.x
        for _ in range(12):
            model.tick()
        assert model.x > start_x, f"{profile.name}: Walk right should move pet rightwards (x increased from {start_x} to {model.x})"

        # Test walk left
        model.set_action("walk_left" if "walk_left" in profile.actions else "walk", direction_right=False)
        start_x = model.x
        for _ in range(12):
            model.tick()
        assert model.x < start_x, f"{profile.name}: Walk left should move pet leftwards (x decreased from {start_x} to {model.x})"

    print("[PASS] test_walk_movement_dx_dy")


def test_default_pet_persistence():
    test_cfg_path = "assets/test_default.json"
    if os.path.exists(test_cfg_path):
        os.remove(test_cfg_path)

    registry = PetRegistry("assets", config_path=test_cfg_path)
    all_pets = [p.id for p in registry.list_all()]
    assert len(all_pets) > 0

    target_pet = all_pets[-1]
    success = registry.set_default_pet(target_pet)
    assert success is True
    assert registry.default_pet_id == target_pet
    assert os.path.exists(test_cfg_path)

    # Re-instantiate to test persistence
    registry2 = PetRegistry("assets", config_path=test_cfg_path)
    assert registry2.default_pet_id == target_pet

    # Test setting default pet to "None"
    success_none = registry.set_default_pet("None")
    assert success_none is True
    assert registry.default_pet_id == "None"
    registry_none = PetRegistry("assets", config_path=test_cfg_path)
    assert registry_none.default_pet_id == "None"
    assert registry_none.get("None") is None

    if os.path.exists(test_cfg_path):
        os.remove(test_cfg_path)

    # Test default registry config_path points to assets/default.json
    reg_default = PetRegistry("assets")
    assert reg_default.config_path == "assets/default.json"
    print("[PASS] test_default_pet_persistence")


def test_lazy_sprite_loading():
    from PyQt6.QtWidgets import QApplication
    from ui.pet_widget import SpriteCache, LazyActionSprites
    app = QApplication.instance() or QApplication([])

    registry = PetRegistry("assets")
    profile = registry.list_all()[0]

    sprites = SpriteCache.get_action_sprites(profile, 128)
    assert isinstance(sprites, LazyActionSprites)
    assert len(sprites._action_frames) == 0  # Zero frames loaded upfront!

    # On-demand loading of idle
    idle_frames = sprites.get("idle")
    assert len(idle_frames) > 0
    assert "idle" in sprites._action_frames
    print("[PASS] test_lazy_sprite_loading")


def test_all_animations_and_events_executable():
    import json
    registry = PetRegistry("assets")
    for profile in registry.list_all():
        anim_path = os.path.join("assets", profile.name, "animation.json")
        with open(anim_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        model = PetModel(profile=profile, x=300, y=300, width=128, height=128)
        model.update_screen_bounds(min_x=0, max_x=1920, floor_y=1080, ceiling_y=0)

        # 1. Mọi hành động khai báo trong animation.json phải được nạp và tick mượt mà
        for a in data.get("animations", []):
            k = a.get("key")
            if not k:
                continue
            assert k in profile.actions, f"{profile.name}: animation '{k}' chưa được nạp vào profile.actions"
            model.set_action(k)
            assert model.active_animation_key in profile.actions
            model.tick()
            model.tick()

        # 2. Kiểm tra sự kiện tương tác TAP (nếu có khai báo events)
        if profile.events:
            model.y = model.floor_y
            model.set_action("idle")
            assert model.handle_event("TAP") is True, f"{profile.name}: TAP event trên mặt đất thất bại"

            model.y = model.ceiling_y
            assert model.handle_event("TAP") is True, f"{profile.name}: TAP event trên trần thất bại"

    print("[PASS] test_all_animations_and_events_executable")


def test_memory_cleanup_on_pet_remove():
    from PyQt6.QtWidgets import QApplication
    from backend.pet_manager import PetManager
    from ui.pet_widget import SpriteCache
    app = QApplication.instance() or QApplication([])

    pm = PetManager("assets")
    pet = pm.spawn_pet("Snoopy")
    assert pet is not None
    assert len(pm.pets) == 1
    # Trigger sprite loading
    pet.get_current_pixmap()
    assert len(SpriteCache._pixmap_cache) > 0

    # Remove the pet -> should clear SpriteCache because 0 pets left
    pm.remove_pet(pet)
    assert len(pm.pets) == 0
    assert len(SpriteCache._pixmap_cache) == 0
    assert len(SpriteCache._action_cache) == 0
    print("[PASS] test_memory_cleanup_on_pet_remove")


def test_tray_icon_scrollable_menus():
    from PyQt6.QtWidgets import QApplication
    from backend.pet_manager import PetManager
    from ui.tray_icon import TrayIcon

    app = QApplication.instance() or QApplication([])
    pm = PetManager("assets")
    tray = TrayIcon(pm)

    assert tray.add_list is not None
    assert tray.add_list.count() == len(pm.registry.profiles)
    assert tray.add_list.height() == 270

    assert tray.default_list is not None
    assert tray.default_list.count() == len(pm.registry.profiles) + 2

    pm.set_default_pet("None")
    assert "None" in tray.default_menu.title()
    assert tray.default_items["None"].text().startswith("✓")

    pm.remove_all_pets()
    print("[PASS] test_tray_icon_scrollable_menus")


if __name__ == "__main__":
    test_dynamic_registry_loading()
    test_pet_physics_and_fall()
    test_climb_and_ceiling()
    test_drag_and_drop()
    test_walk_movement_dx_dy()
    test_default_pet_persistence()
    test_lazy_sprite_loading()
    test_all_animations_and_events_executable()
    test_memory_cleanup_on_pet_remove()
    test_tray_icon_scrollable_menus()
    print("All dynamic asset pet logic tests passed successfully!")
