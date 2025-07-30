import os
import sys
import shutil
import subprocess

def build_windows_app():
    """构建Windows应用程序"""
    print("开始构建Windows应用程序...")
    
    # 创建assets目录（如果不存在）
    if not os.path.exists('assets'):
        os.makedirs('assets')
    
    # 创建logo文件（如果不存在）
    logo_path = os.path.join('assets', 'logo.png')
    if not os.path.exists(logo_path):
        # 创建一个简单的占位图像
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new('RGBA', (200, 200), color=(255, 255, 255, 0))
            d = ImageDraw.Draw(img)
            d.ellipse((10, 10, 190, 190), fill=(41, 128, 185))
            d.ellipse((50, 50, 150, 150), fill=(255, 255, 255))
            d.text((70, 90), "ET", fill=(41, 128, 185), font=ImageFont.truetype("arial.ttf", 36))
            img.save(logo_path)
            print(f"创建了默认logo: {logo_path}")
        except Exception as e:
            print(f"无法创建默认logo: {str(e)}")
            # 如果PIL不可用或出错，创建一个空文件
            with open(logo_path, 'wb') as f:
                f.write(b'')
    
    # 检查PyInstaller是否已安装
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 构建spec文件
    spec_content = f'''\
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['{os.path.abspath(os.getcwd())}'],
    binaries=[],
    datas=[('design.kv', '.'), ('assets', 'assets')],
    hiddenimports=['kivy', 'kivy.core.window.window_sdl2', 'kivy.core.text.text_sdl2', 'kivy.core.video.video_ffpyplayer',
                   'kivy.core.audio.audio_sdl2', 'kivy.core.image.img_sdl2', 'kivy.core.clipboard.clipboard_sdl2',
                   'kivy.core.camera', 'kivy.core.camera.camera_opencv', 'cv2', 'pyzbar', 'pytesseract', 'sqlite3',
                   'requests', 'datetime', 're', 'json'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='条码扫描与生产日期识别',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.png',
)
'''
    
    with open('expiry_tracker.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    # 运行PyInstaller
    print("正在使用PyInstaller构建应用程序...")
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "expiry_tracker.spec"])
    
    print("\n构建完成！")
    print(f"可执行文件位于: {os.path.abspath(os.path.join('dist', '条码扫描与生产日期识别.exe'))}")

if __name__ == "__main__":
    build_windows_app()