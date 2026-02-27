#!/bin/bash
# maomao 影视聚合一键部署脚本 (V1.0.0 版)
# 适用环境：OpenWrt / Linux / 各种 NAS

echo "======================================================="
echo " 🎬 正在为您部署 maomao 聚合影视库 ..."
echo "======================================================="

# 1. 环境自检
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
    echo "❌ 严重错误：未检测到 docker 或 docker-compose！"
    echo "💡 请先在您的系统 / 路由器 / NAS 中安装 Docker 环境后再运行本脚本。"
    exit 1
fi

# 2. 智能工作目录探测 (防套娃核心逻辑)
CURRENT_DIR_NAME=$(basename "$(pwd)")
if [ "$CURRENT_DIR_NAME" = "maomao" ]; then
    # 如果用户已经在名为 maomao 的目录下了，就直接原地安装
    WORK_DIR="$(pwd)"
    echo "[*] 检测到已在 maomao 目录，将执行原地覆盖升级..."
else
    # 否则，在当前目录下新建 maomao 文件夹
    WORK_DIR="$(pwd)/maomao"
    mkdir -p "${WORK_DIR}"
    echo "[*] 已创建全新工作目录: ${WORK_DIR}"
fi
cd "${WORK_DIR}"

# 3. 下载核心代码 (加入国内 Github 加速节点)
echo "[*] 正在通过高速通道下载核心引擎代码..."
wget -qO app.py https://ghproxy.net/https://raw.githubusercontent.com/sillre/maomao/main/app.py

if [ ! -s "app.py" ]; then
    echo "❌ 下载代码失败！请检查网络，或尝试开启科学上网。"
    exit 1
fi
echo "✅ 代码下载成功！"

# 4. 自动生成 Dockerfile (锁定国内镜像源)
echo "[*] 正在生成 Dockerfile..."
cat << 'EOF' > Dockerfile
FROM python:3.9-alpine
WORKDIR /app
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple flask requests
COPY app.py /app/app.py
EXPOSE 8080
CMD ["python", "app.py"]
EOF

# 5. 自动生成 docker-compose.yml (开启热更新映射)
echo "[*] 正在生成 docker-compose.yml (含热更新黑科技)..."
cat << 'EOF' > docker-compose.yml
version: '3'
services:
  maomao:
    build: .
    container_name: maomao
    restart: always
    ports:
      - "8787:8080"
    environment:
      - TZ=Asia/Shanghai
    volumes:
      - ./app.py:/app/app.py
EOF

echo "[*] 环境文件生成完毕！"
echo ""
echo "======================================================="
echo " 🚀 正在全自动构建并启动容器，请稍候..."
echo " ⏳ (受国内网络影响，拉取 Python 环境可能需要 1-3 分钟，请勿关闭窗口)"
echo "======================================================="

# 6. 自动启动
docker-compose down 2>/dev/null
docker-compose up -d --build

# 7. 结果校验
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 部署大功告成！"
    echo "📺 请在 VidHub 或 Infuse 中添加 WebDAV："
    echo "👉 地址: http://您的路由器IP:8787"
    echo "👉 账号密码: 留空即可"
    echo "-------------------------------------------------------"
    echo "💡 极客提示：未来想更新系统，只需用新版 app.py 覆盖当前目录下的文件，"
    echo "   然后执行命令: docker restart maomao 即可瞬间生效，无需重装！"
else
    echo ""
    echo "❌ 启动失败！通常是因为 Docker Hub 镜像拉取超时导致。"
    echo "💡 建议方案：请在您的路由器后台配置 Docker 国内镜像加速器后重试。"
fi
