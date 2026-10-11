"""
Script đóng gói ứng dụng Shimeji Desktop Pet thành tệp thực thi .exe bằng PyInstaller.
Tối ưu hóa:
- Mặc định tạo 1 file .exe duy nhất (One-File) kèm thư mục 'assets/' đặt cạnh file .exe.
- Có tùy chọn --onedir nếu muốn đóng gói dạng thư mục phân phối.
- Tự động chuyển đổi assets/app_icon.png thành app_icon.ico để gán icon cho file .exe.
- Ẩn cửa sổ Console đen (chế độ Windowed/NoConsole).
- Tự động kiểm tra và cài đặt pyinstaller / pillow nếu máy chưa có.
- Loại bỏ các thư viện AI/Machine learning nặng không liên quan để exe nhẹ và mở nhanh.

Cách dùng:
  python build.py            # Đóng gói thành 1 file ShimejiPet.exe duy nhất (mặc định)
  python build.py --onedir   # Đóng gói dạng thư mục phân phối (One-Directory)
  python build.py --clean    # Dọn dẹp cache build và dist cũ trước khi đóng gói
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

# Đảm bảo in tiếng Việt trên console Windows không bị UnicodeEncodeError
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def ensure_dependencies():
    """Tự động kiểm tra và cài đặt các phụ thuộc cần thiết cho quá trình build."""
    required = []
    try:
        import PyInstaller
    except ImportError:
        required.append("pyinstaller>=6.0.0")

    try:
        from PIL import Image
    except ImportError:
        required.append("pillow>=9.0.0")

    if required:
        print(f"[*] Đang cài đặt gói phụ thuộc còn thiếu: {', '.join(required)}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *required])
            print("[✔] Cài đặt gói phụ thuộc hoàn tất.")
        except Exception as e:
            print(f"[!] Cảnh báo: Lỗi khi tự động cài gói qua pip: {e}")


# Các thư viện nặng cần loại bỏ khỏi quá trình scan của PyInstaller để exe nhẹ và build nhanh
EXCLUDE_MODULES = [
    "torch",
    "torchvision",
    "ultralytics",
    "cv2",
    "scipy",
    "pandas",
    "matplotlib",
    "gradio",
    "fastapi",
    "uvicorn",
    "onnxruntime",
    "tkinter",
    "IPython",
    "jupyter",
    "PIL.TkImaging",
]


def convert_icon_if_needed(project_root: Path) -> Path:
    """Tạo tệp app_icon.ico từ assets/app_icon.png để gắn vào tệp exe."""
    ico_path = project_root / "build" / "app_icon.ico"
    app_icon_png = project_root / "assets" / "app_icon.png"

    source_icon = None
    if app_icon_png.exists():
        source_icon = app_icon_png
    else:
        # Fallback: Tìm thumbnail.webp từ các pet trong assets/
        assets_dir = project_root / "assets"
        if assets_dir.exists():
            for p in assets_dir.iterdir():
                if p.is_dir() and (p / "thumbnail.webp").exists():
                    source_icon = p / "thumbnail.webp"
                    break

    if source_icon and source_icon.exists():
        try:
            from PIL import Image

            # Tạo mới ico nếu chưa có hoặc file nguồn mới hơn
            if not ico_path.exists() or source_icon.stat().st_mtime > ico_path.stat().st_mtime:
                ico_path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.open(source_icon)
                img.save(
                    ico_path,
                    format="ICO",
                    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
                )
                print(f"[+] Đã tạo biểu tượng icon cho ứng dụng: {ico_path}")
            return ico_path
        except Exception as e:
            print(f"[!] Không thể chuyển đổi icon ({e}), sẽ dùng icon mặc định của hệ thống.")

    return None


def copy_companion_folders(dest_dir: Path, project_root: Path):
    """Sao chép thư mục tài nguyên 'assets' đi kèm cạnh file .exe."""
    src = project_root / "assets"
    dst = dest_dir / "assets"

    if not src.exists():
        return

    print(f"[+] Đang sao chép thư mục đi kèm: assets -> {dst}")
    if dst.exists():
        try:
            shutil.rmtree(dst)
        except Exception:
            pass

    # Bỏ qua các file script, cache thừa khi đóng gói
    def ignore_patterns(path, names):
        ignored = []
        for name in names:
            if name.endswith(".py") or name.endswith(".pyc") or name == "__pycache__":
                ignored.append(name)
        return ignored

    shutil.copytree(src, dst, ignore=ignore_patterns, dirs_exist_ok=True)


def build_app(onefile: bool = True, clean: bool = False):
    project_root = Path(__file__).resolve().parent
    os.chdir(project_root)

    ensure_dependencies()

    app_name = "ShimejiPet"
    main_script = project_root / "main.py"

    if clean:
        print("[*] Đang dọn dẹp thư mục build/ và dist/ cũ...")
        shutil.rmtree(project_root / "build", ignore_errors=True)
        shutil.rmtree(project_root / "dist", ignore_errors=True)

    # 1. Chuẩn bị icon
    icon_path = convert_icon_if_needed(project_root)

    # 2. Xây dựng lệnh PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",          # Không hiển thị cửa sổ cmd đen
        "--name", app_name,
        "--distpath", str(project_root / "dist"),
        "--workpath", str(project_root / "build"),
        "--specpath", str(project_root / "build"),
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    if icon_path and icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    # Thêm các module exclude để tối ưu dung lượng và tốc độ
    for mod in EXCLUDE_MODULES:
        cmd.extend(["--exclude-module", mod])

    cmd.append(str(main_script))

    mode_label = "1 file .exe duy nhất (One-File)" if onefile else "Thư mục phân phối (One-Directory)"
    print("=" * 60)
    print(f"[*] Bắt đầu đóng gói '{app_name}' dạng: {mode_label}...")
    print("=" * 60)

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\n[X] Đóng gói thất bại! Vui lòng kiểm tra log lỗi ở trên.")
        sys.exit(result.returncode)

    # 3. Sao chép thư mục 'assets/' cạnh file .exe
    if onefile:
        output_folder = project_root / "dist"
        exe_path = output_folder / f"{app_name}.exe"
    else:
        output_folder = project_root / "dist" / app_name
        exe_path = output_folder / f"{app_name}.exe"

    copy_companion_folders(output_folder, project_root)

    print("\n" + "=" * 60)
    print("[✔] ĐÓNG GÓI THÀNH CÔNG!")
    print(f"[✔] File thực thi: {exe_path}")
    print(f"[✔] Thư mục assets đi kèm: {output_folder / 'assets'}")
    print("Bạn có thể nhấp đúp trực tiếp vào file .exe để trải nghiệm Shimeji Desktop Pet!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Shimeji App thành file .exe")
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Đóng gói dạng thư mục phân phối (One-Directory) thay vì 1 file .exe duy nhất",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Xóa cache build và dist cũ trước khi đóng gói",
    )
    args = parser.parse_args()

    # Mặc định là One-File nếu không chỉ định --onedir
    is_onefile = not args.onedir
    build_app(onefile=is_onefile, clean=args.clean)
