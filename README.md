# Maomao 🎬 (V6.9 版)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

> 基于 WebDAV 的极轻量级“无状态”影视聚合网关，专为 **Apple TV / VidHub / Infuse** 打造。

告别庞大的 NAS 硬盘阵列，抛弃年付阿里云盘/夸克网盘！Maomao 是一个纯 Python 编写的动态流媒体桥接中间件。**只需 30MB 内存**，即可让您的播放器瞬间拥有全网近 30,000 部最新、最高清的精选影视资源。

告别 xiaoya、115、阿里云、夸克、syncnext。可接入网易爆米花、VidHub、Infuse、SenPlayer 等一切支持 WebDAV 的播放器。

*注：由于源站限制，目前主打 1080P 高清秒播，暂非全量 4K 片源。*

---

## ✨ 核心黑科技 (Features)

* **🚀 零存储，即时代理 (JIT)：** 服务端不存储任何视频文件。当您在电视上点击海报播放的瞬间，后台并发穿透全网 10 大影视源站，提取真实直连地址喂给播放器。
* **🧼 M3U8 洗流引擎 (防卡死)：** 针对 Apple TV 解码器极其严苛的特点，独家内置 M3U8 清洗器，自动剔除源站插入的“澳门赌场”等分辨率不一致的广告切片，彻底解决音画不同步与播放卡死问题。
* **🛡️ 解说粉碎机：** 双重校验机制（名称正则拦截 + 视频真实时长累加检测），低于 15 分钟的视频直接判定为解说或预告片，自动抛弃并切换下一节点。
* **📂 极简海报墙架构：** 告别一层套一层的反人类文件夹。直接利用豆瓣 API 动态生成单页热门大片的扁平化海报墙，刷片极其丝滑，且自带防封禁拟人化延时。
* **🐳 极度轻量：** 专为 OpenWrt 等弱性能软路由设计，Docker 容器常驻内存极低。

---
## 📜 声明与协议

- **开源协议**：本项目基于 **MIT License** 协议开源。
- **技术研究**：本项目仅作为技术学习与 HTTP/WebDAV 协议研究之用。
- **免责声明**：程序本身不存储、不提供、不分发任何影视实体文件。所有数据均通过 JIT 技术来自互联网公开接口即时代理。用户在使用过程中请遵守当地法律法规。




## 🚀 部署指南 (一键安装)

本程序完美支持 OpenWrt、群晖、威联通或任何带有 Docker 环境的 Linux 服务器。

### 1. 登录终端
使用 SSH 工具连接到您的软路由或 Linux 物理机。

### 2. 执行一键安装脚本
直接复制以下整行命令并回车，脚本将自动拉取代码、构建镜像并在后台启动：

```bash
bash <(curl -s [https://raw.githubusercontent.com/sillre/maomao/main/install_maomao.sh](https://raw.githubusercontent.com/sillre/maomao/main/install_maomao.sh))
---
