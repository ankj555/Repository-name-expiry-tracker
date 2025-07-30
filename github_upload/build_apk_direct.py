#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接构建Android APK的脚本
使用python-for-android (p4a) 工具链
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, cwd=None):
    """运行命令并返回结果"""
    print(f"执行命令: {cmd}")
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd,
            capture_output=True, 
            text=True,
            encoding='utf-8'
        )
        if result.returncode != 0:
            print(f"错误: {result.stderr}")
            return False
        print(f"输出: {result.stdout}")
        return True
    except Exception as e:
        print(f"执行命令时出错: {e}")
        return False

def install_dependencies():
    """安装必要的依赖"""
    print("\n=== 安装构建依赖 ===")
    
    # 安装python-for-android
    deps = [
        "python-for-android",
        "cython",
        "colorama",
        "appdirs",
        "sh",
        "jinja2",
        "six"
    ]
    
    for dep in deps:
        print(f"安装 {dep}...")
        if not run_command(f"pip install {dep}"):
            print(f"安装 {dep} 失败")
            return False
    
    return True

def check_android_sdk():
    """检查Android SDK"""
    print("\n=== 检查Android SDK ===")
    
    # 检查环境变量
    android_home = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not android_home:
        print("❌ 未找到ANDROID_HOME或ANDROID_SDK_ROOT环境变量")
        print("请安装Android SDK并设置环境变量")
        return False
    
    print(f"✅ Android SDK路径: {android_home}")
    return True

def build_apk():
    """构建APK"""
    print("\n=== 开始构建APK ===")
    
    # 获取当前目录
    current_dir = Path.cwd()
    print(f"当前目录: {current_dir}")
    
    # 检查必要文件
    required_files = ['main.py', 'buildozer.spec']
    for file in required_files:
        if not (current_dir / file).exists():
            print(f"❌ 缺少必要文件: {file}")
            return False
    
    # 尝试使用p4a构建
    print("尝试使用python-for-android构建...")
    
    # 创建构建命令
    cmd = [
        "p4a", "apk",
        "--private", ".",
        "--package", "com.expirytracker.app",
        "--name", "保质期追踪器",
        "--version", "1.0",
        "--bootstrap", "sdl2",
        "--requirements", "python3,kivy,pandas,openpyxl,xlrd,pillow,requests",
        "--permission", "CAMERA",
        "--permission", "WRITE_EXTERNAL_STORAGE",
        "--permission", "READ_EXTERNAL_STORAGE",
        "--arch", "arm64-v8a",
        "--release"
    ]
    
    cmd_str = " ".join(cmd)
    print(f"构建命令: {cmd_str}")
    
    if run_command(cmd_str):
        print("✅ APK构建成功!")
        return True
    else:
        print("❌ APK构建失败")
        return False

def main():
    """主函数"""
    print("=== 保质期追踪器 Android APK 构建工具 ===")
    print("此工具将尝试直接构建Android APK文件")
    print()
    
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("❌ 需要Python 3.7或更高版本")
        return False
    
    print(f"✅ Python版本: {sys.version}")
    
    # 安装依赖
    if not install_dependencies():
        print("❌ 依赖安装失败")
        return False
    
    # 检查Android SDK
    if not check_android_sdk():
        print("❌ Android SDK检查失败")
        print("\n解决方案:")
        print("1. 安装Android Studio")
        print("2. 设置ANDROID_HOME环境变量")
        print("3. 或使用GitHub Actions自动构建")
        return False
    
    # 构建APK
    if build_apk():
        print("\n🎉 APK构建完成!")
        print("APK文件位置: dist/")
        return True
    else:
        print("\n❌ APK构建失败")
        print("\n建议使用以下替代方案:")
        print("1. GitHub Actions自动构建")
        print("2. WSL2 + Ubuntu环境")
        print("3. Linux虚拟机")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n用户取消构建")
        sys.exit(1)
    except Exception as e:
        print(f"\n构建过程中出现错误: {e}")
        sys.exit(1)