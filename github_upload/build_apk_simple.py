#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的APK构建解决方案
使用KivyMD打包工具，无需Android SDK
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import zipfile
import json

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
            return False, result.stderr
        print(f"输出: {result.stdout}")
        return True, result.stdout
    except Exception as e:
        print(f"执行命令时出错: {e}")
        return False, str(e)

def create_android_package():
    """创建Android包结构"""
    print("\n=== 创建Android包结构 ===")
    
    # 创建输出目录
    output_dir = Path("android_package")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()
    
    # 复制应用文件
    app_files = [
        "main.py",
        "design.kv",
        "database.py",
        "product_manager.py",
        "barcode_scanner.py",
        "date_recognizer.py",
        "ocr_processor.py",
        "requirements.txt"
    ]
    
    for file in app_files:
        if Path(file).exists():
            shutil.copy2(file, output_dir / file)
            print(f"✅ 复制文件: {file}")
        else:
            print(f"⚠️ 文件不存在: {file}")
    
    # 复制assets目录
    if Path("assets").exists():
        shutil.copytree("assets", output_dir / "assets")
        print("✅ 复制assets目录")
    
    return output_dir

def create_manifest():
    """创建Android清单文件"""
    print("\n=== 创建Android清单 ===")
    
    manifest_content = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.expirytracker.app"
    android:versionCode="1"
    android:versionName="1.0">
    
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.INTERNET" />
    
    <application
        android:label="保质期追踪器"
        android:icon="@drawable/icon"
        android:theme="@android:style/Theme.NoTitleBar">
        
        <activity
            android:name=".MainActivity"
            android:label="保质期追踪器"
            android:screenOrientation="portrait"
            android:configChanges="keyboardHidden|orientation">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>'''
    
    with open("android_package/AndroidManifest.xml", "w", encoding="utf-8") as f:
        f.write(manifest_content)
    
    print("✅ 创建AndroidManifest.xml")

def create_build_script():
    """创建构建脚本"""
    print("\n=== 创建构建脚本 ===")
    
    build_script = '''#!/bin/bash
# Android APK构建脚本

echo "=== 保质期追踪器 Android APK 构建 ==="

# 检查buildozer
if ! command -v buildozer &> /dev/null; then
    echo "安装buildozer..."
    pip install buildozer
fi

# 检查cython
if ! command -v cython &> /dev/null; then
    echo "安装cython..."
    pip install cython
fi

# 构建APK
echo "开始构建APK..."
buildozer android debug

if [ $? -eq 0 ]; then
    echo "✅ APK构建成功!"
    echo "APK位置: bin/"
    ls -la bin/*.apk
else
    echo "❌ APK构建失败"
    exit 1
fi
'''
    
    with open("android_package/build.sh", "w", encoding="utf-8") as f:
        f.write(build_script)
    
    print("✅ 创建build.sh")

def create_docker_solution():
    """创建Docker构建解决方案"""
    print("\n=== 创建Docker构建解决方案 ===")
    
    dockerfile_content = '''FROM ubuntu:20.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    zip \
    unzip \
    openjdk-8-jdk \
    autoconf \
    libtool \
    pkg-config \
    zlib1g-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libtinfo5 \
    cmake \
    libffi-dev \
    libssl-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 安装Android SDK
RUN mkdir -p $ANDROID_HOME && \
    cd $ANDROID_HOME && \
    wget https://dl.google.com/android/repository/commandlinetools-linux-8512546_latest.zip && \
    unzip commandlinetools-linux-8512546_latest.zip && \
    rm commandlinetools-linux-8512546_latest.zip

# 安装Python依赖
RUN pip3 install buildozer cython

# 设置工作目录
WORKDIR /app

# 复制应用文件
COPY . /app/

# 构建APK
CMD ["buildozer", "android", "debug"]
'''
    
    with open("Dockerfile", "w", encoding="utf-8") as f:
        f.write(dockerfile_content)
    
    # 创建Docker构建脚本
    docker_build_script = '''@echo off
echo === Docker APK构建 ===
echo.
echo 此脚本将使用Docker构建Android APK
echo 请确保已安装Docker Desktop
echo.

:: 构建Docker镜像
echo 构建Docker镜像...
docker build -t expiry-tracker-builder .

if %errorlevel% neq 0 (
    echo ❌ Docker镜像构建失败
    pause
    exit /b 1
)

:: 运行构建
echo 开始构建APK...
docker run --rm -v %cd%\bin:/app/bin expiry-tracker-builder

if %errorlevel% equ 0 (
    echo ✅ APK构建成功!
    echo APK位置: bin\\*.apk
    dir bin\\*.apk
) else (
    echo ❌ APK构建失败
)

pause
'''
    
    with open("build_with_docker.bat", "w", encoding="utf-8") as f:
        f.write(docker_build_script)
    
    print("✅ 创建Dockerfile和Docker构建脚本")

def create_github_action_trigger():
    """创建GitHub Actions触发脚本"""
    print("\n=== 创建GitHub Actions触发脚本 ===")
    
    github_script = '''@echo off
echo === GitHub Actions APK构建 ===
echo.
echo 此脚本将帮助您使用GitHub Actions构建APK
echo.

echo 步骤:
echo 1. 创建GitHub仓库
echo 2. 推送代码到仓库
echo 3. GitHub Actions自动构建APK
echo 4. 从Actions页面下载APK
echo.

echo 推送命令:
echo git init
echo git add .
echo git commit -m "Initial commit"
echo git branch -M main
echo git remote add origin https://github.com/YOUR_USERNAME/expiry-tracker.git
echo git push -u origin main
echo.

echo 构建完成后，访问:
echo https://github.com/YOUR_USERNAME/expiry-tracker/actions
echo.

pause
'''
    
    with open("github_build_guide.bat", "w", encoding="utf-8") as f:
        f.write(github_script)
    
    print("✅ 创建GitHub Actions指南")

def create_web_app_alternative():
    """创建Web应用替代方案"""
    print("\n=== 创建Web应用替代方案 ===")
    
    # 创建简单的Web版本
    web_html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>保质期追踪器 - Web版</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .feature {
            margin: 20px 0;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
        }
        .btn:hover {
            background-color: #45a049;
        }
        .download-section {
            background-color: #e7f3ff;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🍎 保质期追踪器</h1>
        
        <div class="download-section">
            <h2>📱 下载APK</h2>
            <p>由于技术限制，我们提供以下获取APK的方案：</p>
            
            <div class="feature">
                <h3>🚀 GitHub Actions自动构建（推荐）</h3>
                <p>1. 将代码推送到GitHub仓库</p>
                <p>2. GitHub自动构建APK</p>
                <p>3. 从Actions页面下载</p>
                <button class="btn" onclick="window.open('https://github.com')">访问GitHub</button>
            </div>
            
            <div class="feature">
                <h3>🐳 Docker构建</h3>
                <p>使用Docker在本地构建APK</p>
                <button class="btn" onclick="alert('运行 build_with_docker.bat')">Docker构建</button>
            </div>
            
            <div class="feature">
                <h3>💻 Web版本（当前）</h3>
                <p>直接在浏览器中使用保质期追踪功能</p>
                <button class="btn" onclick="startWebApp()">开始使用</button>
            </div>
        </div>
        
        <div id="webapp" style="display:none;">
            <h2>📋 产品管理</h2>
            <input type="text" id="productName" placeholder="产品名称" style="width:200px; padding:5px;">
            <input type="date" id="expiryDate" style="padding:5px;">
            <button class="btn" onclick="addProduct()">添加产品</button>
            
            <div id="productList" style="margin-top:20px;"></div>
        </div>
    </div>
    
    <script>
        function startWebApp() {
            document.getElementById('webapp').style.display = 'block';
        }
        
        function addProduct() {
            const name = document.getElementById('productName').value;
            const date = document.getElementById('expiryDate').value;
            
            if (name && date) {
                const list = document.getElementById('productList');
                const item = document.createElement('div');
                item.className = 'feature';
                item.innerHTML = `<strong>${name}</strong> - 过期日期: ${date}`;
                list.appendChild(item);
                
                document.getElementById('productName').value = '';
                document.getElementById('expiryDate').value = '';
            }
        }
    </script>
</body>
</html>'''
    
    with open("web_app.html", "w", encoding="utf-8") as f:
        f.write(web_html)
    
    print("✅ 创建Web应用版本")

def main():
    """主函数"""
    print("=== 保质期追踪器 APK构建解决方案 ===")
    print("正在创建多种构建方案...")
    print()
    
    try:
        # 创建Android包结构
        output_dir = create_android_package()
        
        # 创建清单文件
        create_manifest()
        
        # 创建构建脚本
        create_build_script()
        
        # 创建Docker解决方案
        create_docker_solution()
        
        # 创建GitHub Actions指南
        create_github_action_trigger()
        
        # 创建Web应用替代方案
        create_web_app_alternative()
        
        print("\n🎉 解决方案创建完成!")
        print("\n📋 可用的构建方案:")
        print("1. 🚀 GitHub Actions: 运行 github_build_guide.bat")
        print("2. 🐳 Docker构建: 运行 build_with_docker.bat")
        print("3. 💻 Web版本: 打开 web_app.html")
        print("4. 📱 Android包: 查看 android_package/ 目录")
        
        print("\n推荐使用GitHub Actions方案，完全免费且自动化!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 创建解决方案时出错: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ 所有解决方案已准备就绪!")
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        sys.exit(1)