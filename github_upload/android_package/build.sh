#!/bin/bash
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
