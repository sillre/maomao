#!/bin/bash
# ==========================================
# Maomao WebDAV 影视引擎 一键安装部署脚本
# 版本: V1.0.3 (开源满血版)
# ==========================================

echo "======================================================="
echo " 🚀 开始安装 Maomao WebDAV 影视聚合引擎 V1.0.3"
echo "======================================================="

# 1. 环境自检
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
    echo "❌ 严重错误：未检测到 docker 或 docker-compose！"
    echo "💡 请先在您的系统中安装 Docker 环境后再运行本脚本。"
    exit 1
fi

# 2. 交互式配置 TMDB KEY
echo -e "\n-------------------------------------------------------"
echo "🌟 【可选配置】: TMDB API Key"
echo "如果您拥有 TMDB API Key，系统每天会自动为您抓取全网最新上映的影视数据。"
echo "如果您没有，请直接按回车跳过，系统将完美使用自带的「纯净万部离线片库」！"
read -p "👉 请输入您的 TMDB API Key (按回车跳过): " USER_TMDB_KEY
echo "-------------------------------------------------------"

# 3. 创建工作目录
INSTALL_DIR="$(pwd)/maomao-webdav"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

GITHUB_RAW_URL="https://raw.githubusercontent.com/sillre/maomao/main"

echo -e "\n[*] 正在下载核心引擎代码..."
wget -qO app.py "$GITHUB_RAW_URL/app.py"

echo "[*] 正在下载万部离线预置片库 (免配置核心)..."
wget -qO tmdb_massive_lib_v7.json "$GITHUB_RAW_URL/tmdb_massive_lib_v7.json"

if [ ! -s "app.py" ]; then
    echo "❌ 下载核心代码失败！请检查网络连接或尝试开启代理。"
    exit 1
fi

# 4. 动态生成 Docker 配置文件
echo "[*] 正在为您动态生成 Docker 配置文件..."

# 巧妙处理空字符串的情况
ENV_TMDB=""
if [ -n "$USER_TMDB_KEY" ]; then
    ENV_TMDB="- TMDB_KEY=${USER_TMDB_KEY}"
    echo "✅ 已注入 TMDB API Key，【每日自动进化模式】已就绪！"
else
    echo "✅ 未检测到 Key，【内置万部离线片库模式】已启用，开箱即用！"
fi

cat << EOF > docker-compose.yml
version: '3.8'

services:
  maomao-webdav:
    image: python:3.9-slim
    container_name: maomao-webdav
    working_dir: /app
    volumes:
      - .:/app
    ports:
      - "8787:8080"
    environment:
      - TZ=Asia/Shanghai
      ${ENV_TMDB}
    command: >
      bash -c "pip install -q flask requests urllib3 && python app.py"
    restart: unless-stopped
EOF

# 5. 启动容器
echo -e "\n[*] 正在拉取 Python 环境并启动 Docker 容器 (可能需要 1-2 分钟)..."
docker-compose down 2>/dev/null
docker-compose up -d

if [ $? -eq 0 ]; then
    echo "======================================================="
    echo "🎉 安装圆满完成！您的个人影视中枢已在运行中。"
    echo "📺 请在 Apple TV / 电脑播放器 (VidHub, Infuse 等) 中添加 WebDAV："
    echo "   👉 地址: http://您的设备IP:8787"
    echo "   👉 账号/密码: 无需填写，直接连接"
    echo "======================================================="
else
    echo "❌ 启动失败！通常是因为 Docker 镜像拉取超时，请检查网络。"
fi
