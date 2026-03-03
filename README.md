<div align="center">

# 🎬 Maomao WebDAV 

*基于 WebDAV 协议的极轻量级“无状态”影视聚合网关*

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)
[![Release](https://img.shields.io/badge/Release-V1.0.3_开源满血版-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

专为 **Apple TV / VidHub / Infuse / 网易爆米花** 打造的终极万部级私人影院解决方案。

</div>

---

> **告别庞大的 NAS 硬盘阵列，抛弃年付的阿里云盘与夸克网盘！**
> Maomao 是一个纯 Python 编写的动态流媒体桥接中间件。只需 **30MB** 内存，即可让您的播放器瞬间拥有全网近万部最新、最高清的精选影视资源。永不失效，即点即播！

*注：由于源站限制，目前主打 1080P 高清秒播，暂非全量 4K 片源。*

## ✨ V1.0.3 核心黑科技 

* ⚡️ **动态能效比测速探针**
    **彻底击碎晚高峰卡顿魔咒！** 首创秒表测速机制。当您点击播放时，系统并发向全网发射 HEAD 探针，不仅测量真实切片体积（防假高清），更计算网络延迟。以 `(体积/延迟)` 的能效比作为最终排名，物理剔除“假死/超慢”的 CDN 节点。

* 🛡️ **SSL 降维防弹衣**
    专为极其严苛的 Apple tvOS 安全机制打造。拦截所有 HTTPS 盗版源的过期/野鸡证书，强制降级直连源为 HTTP，彻底解决 Apple TV 播放时频发的“网络异常”问题。

* 🔪 **纯净双轨切源系统 (无状态)**
    抛弃容易引发死循环的臃肿“续播记忆”。
    * **电影**：利用伪装后缀完美触发高级播放器的版本折叠菜单，手动秒切画质（4K / 1080P / 720P）。
    * **剧集**：恢复单集单文件，利用 `3秒~60秒` 黄金窗口期，只需在电视上退出重进即可瞬间完成源站切换；超过 60 秒则自动重置回最优源。

* 🛑 **绝对净网过滤器**
    内置强悍的本地日期校验与正则表达式，彻底抹杀 TMDB 接口返回的“未来未公映影片”及国内无法搜索的“纯英文冷门剧”，确保海报墙 **100% 可播放**。

* 📦 **离线片库支持 (开箱即用)**
    自带万部经过严格清洗的离线纯净数据库 (v7)。**小白用户完全不需要配置 TMDB API Key** 即可完美运行，彻底抹平使用门槛！

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
curl -s https://raw.githubusercontent.com/sillre/maomao/main/install_maomao.sh | bash
```
(💡 运行后，您可以选择填入自己的 TMDB Key 开启每日自动抓取，或直接回车使用内置离线片库)
### 3. 配置播放器

安装完成后，打开您的手机或电视播放器（网易爆米花、VidHub、Infuse、SenPlayer 等一切支持 WebDAV 的播放器）：

导航至 添加文件源 -> 添加 WebDAV (或 HTTP)

地址 / URL：http://您的设备IP:8787 (例如 http://192.168.1.1:8787)

用户名：留空（如果报错请尝试填写 admin）

密码：留空

### 🛠️ 更新指南

老用户请重新执行一次一键安装命令以获取  Maomao 

无需漫长的 build 重构，1秒钟瞬间生效，立刻享受您的终极万部级私人影院！🍿
