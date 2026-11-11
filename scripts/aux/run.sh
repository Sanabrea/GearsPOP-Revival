#!/bin/zsh
# Restarts the game in the emulator and shows the relevant logcat lines after N seconds (default 50)
ADB=/opt/homebrew/share/android-commandlinetools/platform-tools/adb
$ADB shell am force-stop com.microsoft.gearspop; $ADB logcat -c
$ADB shell am start -n com.microsoft.gearspop/com.appboy.unity.AppboyUnityPlayerActivity >/dev/null
sleep ${1:-50}
$ADB logcat -d | grep -E 'GPDiag|Unity' | grep -E 'CMS served|OK \(|471|CATAPULT|E Unity   : [A-Za-z]|  at Mediatonic|missing|Exception|UNLOADING|LOADING SCENE' | grep -vE 'UnknownHost|LoginRequest' | cut -c32-210 | awk '!s[$0]++' | head -${2:-30}
