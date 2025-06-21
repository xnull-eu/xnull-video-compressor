#!/usr/bin/env python3
"""
Build script for XNull Video Compressor
Creates standalone executables for Windows, macOS, and Linux
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
import importlib.util
import pkg_resources

def check_requirements():
    """Check if required packages are installed"""
    print("Checking requirements...")
    
    required_packages = ['PyQt5', 'ffmpeg-python', 'moviepy', 'psutil']
    missing_packages = []
    
    for package in required_packages:
        try:
            pkg_resources.get_distribution(package)
        except pkg_resources.DistributionNotFound:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Installing missing packages...")
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            print("All required packages installed successfully!")
        except subprocess.CalledProcessError:
            print("Failed to install required packages. Please install them manually:")
            for package in missing_packages:
                print(f"pip install {package}")
            return False
    
    # Check for PyInstaller
    try:
        importlib.util.find_spec('PyInstaller')
    except ImportError:
        print("PyInstaller is not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyInstaller"])
            print("PyInstaller installed successfully!")
        except subprocess.CalledProcessError:
            print("Failed to install PyInstaller. Please install it manually:")
            print("pip install PyInstaller")
            return False
    
    # Verify icon exists
    if not os.path.exists("app_icon.png"):
        print("Warning: app_icon.png not found. The application will use the default icon.")
        print("Please place app_icon.png in the current directory.")
    
    return True

def build_windows():
    """Build for Windows"""
    print("\nBuilding for Windows...")
    
    # Create spec file for better control
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['video_compressor.py'],
             pathex=[{repr(os.getcwd())}],
             binaries=[],
             datas=[('app_icon.png', '.')] if os.path.exists('app_icon.png') else [],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyInstaller', 'pip', 'setuptools', 'wheel', 'pytest'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='XNull_Video_Compressor',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon='app_icon.png' if os.path.exists('app_icon.png') else None )
'''
    
    with open("xnull_video_compressor.spec", "w") as f:
        f.write(spec_content)
    
    # Build using the spec file
    cmd = [
        "pyinstaller",
        "--clean",
        "xnull_video_compressor.spec"
    ]
    
    subprocess.check_call(cmd)
    print("Windows build completed!")

def build_macos():
    """Build for macOS"""
    print("\nBuilding for macOS...")
    
    # Create spec file for better control
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['video_compressor.py'],
             pathex=[{repr(os.getcwd())}],
             binaries=[],
             datas=[('app_icon.png', '.')] if os.path.exists('app_icon.png') else [],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyInstaller', 'pip', 'setuptools', 'wheel', 'pytest'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='XNull_Video_Compressor',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon='app_icon.png' if os.path.exists('app_icon.png') else None )
'''
    
    with open("xnull_video_compressor_macos.spec", "w") as f:
        f.write(spec_content)
    
    # Build using the spec file
    cmd = [
        "pyinstaller",
        "--clean",
        "xnull_video_compressor_macos.spec"
    ]
    
    subprocess.check_call(cmd)
    print("macOS build completed!")

def build_linux():
    """Build for Linux"""
    print("\nBuilding for Linux...")
    
    # Verify icon exists
    if not os.path.exists("app_icon.png"):
        print("Warning: app_icon.png not found. The application will use the default icon.")
    
    # Create spec file for better control
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['video_compressor.py'],
             pathex=[{repr(os.getcwd())}],
             binaries=[],
             datas=[('app_icon.png', '.')] if os.path.exists('app_icon.png') else [],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyInstaller', 'pip', 'setuptools', 'wheel', 'pytest'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='xnull_video_compressor',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False)
'''
    
    with open("xnull_video_compressor_linux.spec", "w") as f:
        f.write(spec_content)
    
    # Build using the spec file
    cmd = [
        "pyinstaller",
        "--clean",
        "xnull_video_compressor_linux.spec"
    ]
    
    subprocess.check_call(cmd)
    
    # Create .desktop file for Linux
    desktop_file = """[Desktop Entry]
Name=XNull Video Compressor
Comment=Compress videos to a specific target size
Exec=xnull_video_compressor
Icon=app_icon
Terminal=false
Type=Application
Categories=Utility;AudioVideo;
"""
    
    os.makedirs("dist/linux", exist_ok=True)
    with open("dist/linux/xnull-video-compressor.desktop", "w") as f:
        f.write(desktop_file)
    
    # Copy icon for Linux
    if os.path.exists("app_icon.png"):
        shutil.copy("app_icon.png", "dist/linux/app_icon.png")
    
    print("Linux build completed!")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Build XNull Video Compressor for different platforms")
    parser.add_argument("--platform", choices=["windows", "macos", "linux", "all"], 
                        default=platform.system().lower(), 
                        help="Target platform (default: current platform)")
    args = parser.parse_args()
    
    if not check_requirements():
        sys.exit(1)
    
    current_platform = platform.system().lower()
    if current_platform == "darwin":
        current_platform = "macos"
    
    # Create build directory
    os.makedirs("build", exist_ok=True)
    os.makedirs("dist", exist_ok=True)
    
    try:
        if args.platform == "all":
            if current_platform == "windows":
                build_windows()
            if current_platform == "macos":
                build_macos()
            if current_platform == "linux":
                build_linux()
            print("\nWarning: Can only build for the current platform. Use separate builds for other platforms.")
        elif args.platform == "windows":
            if current_platform != "windows":
                print("Warning: Building Windows executable on non-Windows platform may not work correctly.")
            build_windows()
        elif args.platform == "macos":
            if current_platform != "macos":
                print("Warning: Building macOS application on non-macOS platform may not work correctly.")
            build_macos()
        elif args.platform == "linux":
            if current_platform != "linux":
                print("Warning: Building Linux executable on non-Linux platform may not work correctly.")
            build_linux()
    except subprocess.CalledProcessError as e:
        print(f"Error during build: {e}")
        sys.exit(1)
    
    print("\nBuild process completed!")
    print("Executable can be found in the 'dist' directory.")

if __name__ == "__main__":
    main() 