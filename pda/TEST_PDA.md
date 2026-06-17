启动模拟器 & 安装 APK
# 将 adb 加入 PATH（方便后续操作）
export PATH=$PATH:~/Library/Android/sdk/platform-tools

# 启动模拟器（可用 Android Studio AVD Manager 点 ▶，或命令行）
~/Library/Android/sdk/emulator/emulator -avd pda_test -netdelay none -netspeed full &

# 确认模拟器已连接
adb devices
# → 应该看到 "emulator-5554   device"

# 构建并安装 debug APK
cd /Users/Yoo/SVN/00.GITHUB/ComsumableManager/pda
./gradlew installDebug

# 验证安装
adb shell pm list packages | grep pda
# → 应该看到 package:com.smes.pda
