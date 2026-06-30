==========================================
# 1. 本地构建 + 更新版本号 + 复制到 web 目录
==========================================
./script/build-apk.sh --version 3.1.0 --build


1. --build	                自动递增：3.1.0 → 3.1.1|
2. --version 4.0.0 --build	使用指定版本：4.0.0
3. --不带任何参数（仅复制）	版本号不变

==========================================
# 2. 部署到两台服务器（带进度条）
==========================================
./script/deploy-apk.sh

# 只部署到某台
./script/deploy-apk.sh --server 1
./script/deploy-apk.sh --server 2

# 先看看要执行什么（不实际部署）
./script/deploy-apk.sh --dry-run

==========================================
# 3. 在开发模拟器上安装APK
==========================================
./script/install-apk.sh				自动找到最新 APK，安装到已连接的设备/模拟器
./script/install-apk.sh --avd pda_test		启动指定 AVD 并安装
./script/install-apk.sh --avd			交互选择 AVD 并安装
./script/install-apk.sh --list			列出所有可用 AVD
./script/install-apk.sh --build			先构建再安装（一步到位）
./script/install-apk.sh --fresh			全新安装（清除应用数据）
./script/install-apk.sh --reinstall		强制重装（保留数据）
./script/install-apk.sh smes-pda.3.0.0.apk	指定旧版本 APK
./script/install-apk.sh --debug			安装 debug 变体

=========================================
# 4.清理构建目录
=========================================
./script/clean-apk.sh			清理旧 APK，每个目录只保留最新 1 个
./script/clean-apk.sh --keep 3		保留最新 3 个版本
./script/clean-apk.sh --all		清理旧 APK + Gradle 构建缓存(840M) + Node 缓存(53M)
./script/clean-apk.sh --build		只清 Gradle 缓存，不动 APK
./script/clean-apk.sh --dry-run		预览模式，先看会删什么		
