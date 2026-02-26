#!/bin/bash
# maomao 影视聚合一键部署脚本
# 适用环境：OpenWrt / Linux (需已安装 Docker 和 Docker-compose)

echo "======================================================="
echo " 🎬 正在为您部署 maomao 聚合影视库 ..."
echo "======================================================="

# 1. 创建工作目录 (动态获取当前路径)
WORK_DIR="$(pwd)/maomao"
mkdir -p ${WORK_DIR}
cd ${WORK_DIR}

# 2. 自动从你的 GitHub 拉取最新代码
echo "[*] 正在从 GitHub 下载核心引擎代码..."
wget -qO app.py https://raw.githubusercontent.com/sillre/maomao/main/app.py

if [ ! -s "app.py" ]; then
    echo "❌ 下载代码失败！请检查网络，或确认 app.py 已经上传到 GitHub。"
    exit 1
fi
echo "✅ 代码下载成功！"

# 3. 自动生成 Dockerfile
echo "[*] 正在生成 Dockerfile..."
cat << 'EOF' > Dockerfile
FROM python:3.9-alpine
WORKDIR /app
RUN pip install --no-cache-dir flask requests beautifulsoup4
COPY app.py /app/app.py
EXPOSE 8080
CMD ["python", "app.py"]
EOF

# 4. 自动生成 docker-compose.yml (✨ 已加入文件映射黑科技)
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
      # 终极黑科技：直接将外面的 app.py 实时映射到容器内部
      - ./app.py:/app/app.py
EOF

echo "[*] 环境文件生成完毕！"
echo ""
echo "======================================================="
echo " 🚀 正在全自动构建并启动容器，请稍候..."
echo "======================================================="

# 5. 自动启动
# 先停止可能存在的旧容器，防止冲突
docker-compose down 2>/dev/null
docker-compose up -d --build

echo ""
echo "🎉 部署大功告成！"
echo "📺 请在 VidHub 或 Infuse 中添加 WebDAV："
echo "👉 地址: http://您的路由器IP:8787"
echo "👉 账号密码: 留空即可"
echo "-------------------------------------------------------"
echo "💡 极客提示：未来想更新系统，只需用新版 app.py 覆盖当前目录下的文件，"
echo "   然后执行命令: docker restart maomao 即可瞬间生效，无需重装！"
