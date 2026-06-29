# 1. 本地构建 + 更新版本号 + 复制到 web 目录
./script/build-apk.sh --version 3.1.0 --build


1. --build	                自动递增：3.1.0 → 3.1.1|
2. --version 4.0.0 --build	使用指定版本：4.0.0
3. --不带任何参数（仅复制）	版本号不变


# 2. 部署到两台服务器（带进度条）
./script/deploy-apk.sh

# 只部署到某台
./script/deploy-apk.sh --server 1
./script/deploy-apk.sh --server 2

# 先看看要执行什么（不实际部署）
./script/deploy-apk.sh --dry-run
