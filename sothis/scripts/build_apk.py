#!/usr/bin/env python3
"""Dependency-light Android build for this Java-only client."""
import argparse
import os
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parent.parent

def run(args):
    subprocess.run([str(x) for x in args],check=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--tools',required=True,type=Path)
    p.add_argument('--android-jar',required=True,type=Path)
    p.add_argument('--ecj',required=True,type=Path)
    p.add_argument('--keystore',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    source=ROOT/'android/app/src/main';build=ROOT/'android/app/build/manual'
    classes=build/'classes';dex=build/'dex'
    classes.mkdir(parents=True,exist_ok=True);dex.mkdir(exist_ok=True)
    resources=build/'resources.zip';base=build/'base.apk';unsigned=build/'unsigned.apk';aligned=build/'aligned.apk'
    run([args.tools/'aapt2','compile','--dir',source/'res','-o',resources])
    run([args.tools/'aapt2','link','-o',base,'--manifest',source/'AndroidManifest.xml','-I',args.android_jar,'-A',source/'assets',resources])
    java=list((source/'java').rglob('*.java'))
    run(['java','-jar',args.ecj,'-8','-bootclasspath',args.android_jar,'-classpath',args.android_jar,'-d',classes,*java])
    run(['java','-cp',args.tools/'lib/d8.jar','com.android.tools.r8.D8','--min-api','26','--lib',args.android_jar,'--output',dex,*classes.rglob('*.class')])
    with zipfile.ZipFile(base) as original,zipfile.ZipFile(unsigned,'w',zipfile.ZIP_DEFLATED) as out:
        for entry in original.infolist():out.writestr(entry,original.read(entry.filename))
        for entry in dex.glob('*.dex'):out.write(entry,entry.name)
    run([args.tools/'zipalign','-f','4',unsigned,aligned])
    if not args.keystore.exists():
        args.keystore.parent.mkdir(parents=True,exist_ok=True)
        run(['keytool','-genkeypair','-keystore',args.keystore,'-storepass','android','-keypass','android','-alias','androiddebugkey','-keyalg','RSA','-keysize','2048','-validity','10000','-dname','CN=Android Debug,O=Android,C=US'])
        args.keystore.chmod(0o600)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    run(['java','-jar',args.tools/'lib/apksigner.jar','sign','--ks',args.keystore,'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',args.output,aligned])
    run(['java','-jar',args.tools/'lib/apksigner.jar','verify','--verbose',args.output])
    run([args.tools/'aapt2','dump','badging',args.output])
    print('APK written:',args.output)

if __name__=='__main__':main()
