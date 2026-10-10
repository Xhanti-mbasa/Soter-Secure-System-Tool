#!/usr/bin/env python3
"""Execute the production scheduling boundary against strict JVM Android test doubles.

This checks failure handling; it is not an emulator/device test. The strict
network-permission double models Android 14's documented JobScheduler exception.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
ANDROID = '{http://schemas.android.com/apk/res/android}'
SOURCES = {
    'android/Manifest.java': '''package android; public final class Manifest {public static final class permission {public static final String ACCESS_NETWORK_STATE="android.permission.ACCESS_NETWORK_STATE";}}''',
    'android/content/pm/PackageManager.java': '''package android.content.pm; public final class PackageManager {public static final int PERMISSION_GRANTED=0;}''',
    'android/content/Context.java': '''package android.content; public abstract class Context {public static final String JOB_SCHEDULER_SERVICE="jobscheduler"; public abstract int checkSelfPermission(String permission); public abstract Object getSystemService(String name);}''',
    'android/content/ComponentName.java': '''package android.content; public final class ComponentName {public ComponentName(Context context,Class<?> service){}}''',
    'android/app/job/JobScheduler.java': '''package android.app.job; public abstract class JobScheduler {public static final int RESULT_SUCCESS=1,RESULT_FAILURE=0;public abstract int schedule(JobInfo job);}''',
    'android/app/job/JobInfo.java': '''package android.app.job; import android.content.ComponentName; public final class JobInfo {public static final int NETWORK_TYPE_ANY=1;public int id,network;public long interval;public boolean persisted;public static final class Builder {private final JobInfo job=new JobInfo();public Builder(int id,ComponentName service){job.id=id;}public Builder setRequiredNetworkType(int network){job.network=network;return this;}public Builder setPeriodic(long interval){job.interval=interval;return this;}public Builder setPersisted(boolean persisted){job.persisted=persisted;return this;}public JobInfo build(){return job;}}}''',
    'za/co/zalens/StartupTest.java': '''package za.co.zalens;
import android.content.Context;import android.content.ComponentName;import android.app.job.*;
public final class StartupTest {
 static final class StrictScheduler extends JobScheduler {
  final boolean permission;final int mode;int calls;JobInfo last;
  StrictScheduler(boolean permission,int mode){this.permission=permission;this.mode=mode;}
  public int schedule(JobInfo job){calls++;last=job;if(!permission)throw new SecurityException("ACCESS_NETWORK_STATE required for network jobs");if(mode==2)throw new SecurityException("Scheduling restricted");if(mode==3)throw new IllegalStateException("Scheduler temporarily unavailable");return mode==1?RESULT_FAILURE:RESULT_SUCCESS;}
 }
 static final class TestContext extends Context {
  final boolean permission;final StrictScheduler scheduler;
  TestContext(boolean permission,int mode){this.permission=permission;scheduler=mode==4?null:new StrictScheduler(permission,mode);}
  public int checkSelfPermission(String name){return permission?0:-1;}
  public Object getSystemService(String name){return scheduler;}
 }
 static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
 public static void main(String[] args){
  TestContext old=new TestContext(false,0);boolean rejected=false;
  try{old.scheduler.schedule(new JobInfo.Builder(202,new ComponentName(old,StartupTest.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(900000).setPersisted(true).build());}catch(SecurityException expected){rejected=true;}
  check(rejected,"Old unguarded configuration must reproduce strict permission rejection");
  TestContext missing=new TestContext(false,0);check(!MonitorScheduler.schedule(missing,StartupTest.class).isEmpty(),"Missing permission must return an error");check(missing.scheduler.calls==0,"Do not attempt a forbidden network job");
  TestContext good=new TestContext(true,0);check(MonitorScheduler.schedule(good,StartupTest.class).isEmpty(),"Permission-correct startup must succeed");
  check(good.scheduler.last.id==202&&good.scheduler.last.network==JobInfo.NETWORK_TYPE_ANY&&good.scheduler.last.interval==900000&&good.scheduler.last.persisted,"Preserve existing job identity and constraints");
  for(int mode=1;mode<=4;mode++)check(!MonitorScheduler.schedule(new TestContext(true,mode),StartupTest.class).isEmpty(),"Scheduler rejection, exceptions and missing service must be nonfatal");
  System.out.println("Native scheduling boundary passed: old permission rejection, correct schedule, missing permission/service, denied schedule, SecurityException and IllegalStateException.");
 }
}'''
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ecj', required=True, type=Path)
    args = parser.parse_args()
    source = ROOT / 'android/app/src/main'
    manifest = ET.parse(source / 'AndroidManifest.xml').getroot()
    permissions = {p.get(ANDROID + 'name') for p in manifest.findall('uses-permission')}
    assert {'android.permission.ACCESS_NETWORK_STATE', 'android.permission.INTERNET', 'android.permission.RECEIVE_BOOT_COMPLETED'} <= permissions
    services = manifest.findall('application/service')
    assert any(s.get(ANDROID + 'name') == '.MonitorJob' and s.get(ANDROID + 'permission') == 'android.permission.BIND_JOB_SERVICE' for s in services)
    activity = (source / 'java/za/co/zalens/MainActivity.java').read_text()
    creation = activity[activity.index('@Override public void onCreate'):activity.index('web.setWebViewClient')]
    assert 'MonitorJob.schedule' not in creation
    assert 'onPageFinished' in activity and 'MonitorJob.schedule' in activity
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        files = []
        for name, content in SOURCES.items():
            file = tmp / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)
            files.append(file)
        classes = tmp / 'classes'
        classes.mkdir()
        files.append(source / 'java/za/co/zalens/MonitorScheduler.java')
        subprocess.run(['java', '-jar', str(args.ecj), '-8', '-d', str(classes), *map(str, files)], check=True)
        subprocess.run(['java', '-cp', str(classes), 'za.co.zalens.StartupTest'], check=True)
    print('Launch permission and JobService declarations verified; optional work begins after the local page loads.')


if __name__ == '__main__':
    main()
