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
# 这里已经为你替换成了真实的 GitHub 地址！
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
EXPOSE 8080
CMD ["python", "app.py"]
EOF

# 4. 自动生成 docker-compose.yml
echo "[*] 正在生成 docker-compose.yml..."
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
				  EOF

				  echo "[*] 环境文件生成完毕！"
				  echo ""
				  echo "======================================================="
				  echo " 🚀 正在全自动构建并启动容器，请稍候..."
				  echo "======================================================="

				  # 5. 自动启动！
			  docker-compose up -d --build

			  echo ""
			  echo "🎉 部署大功告成！"
			  echo "📺 请在 VidHub 或 Infuse 中添加 WebDAV："
			  echo "👉 地址: http://您的路由器IP:8787"
			  echo "👉 账号密码: 留空即可"
