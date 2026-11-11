#!/bin/zsh
# Reconstruye build/GearsPOP_diag.apk desde build/work/dec (con libunity/libil2cpp ya parcheadas) y el servidor en server_diag/.
set -e
cd "$(dirname "$0")/.."
SDK=/opt/homebrew/share/android-commandlinetools; AJ=$SDK/platforms/android-34/android.jar; BT=$SDK/build-tools/34.0.0
export JAVA_HOME=/opt/homebrew/opt/openjdk@17 PATH=/opt/homebrew/opt/openjdk@17/bin:$PATH
O=build/server_diag; W=build/work; rm -rf $O; mkdir -p $O/classes $O/dex
javac --release 8 -nowarn -Xlint:-options -cp $AJ -d $O/classes server_diag/src/gpdiag/*.java
$BT/d8 --min-api 24 --lib $AJ --output $O/dex $(find $O/classes -name '*.class')
rm -f $W/unsigned.apk $W/aligned.apk; apktool b -o $W/unsigned.apk $W/dec 2>&1 | tail -1
cp $O/dex/classes.dex $W/classes2.dex; (cd $W && zip -q unsigned.apk classes2.dex)
$BT/zipalign -f -p 4 $W/unsigned.apk $W/aligned.apk
$BT/apksigner sign --ks build/keys/sign.jks --ks-pass pass:gpdiag-sign --out build/GearsPOP_diag.apk $W/aligned.apk
$BT/apksigner verify build/GearsPOP_diag.apk && echo "APK firmado: build/GearsPOP_diag.apk"
