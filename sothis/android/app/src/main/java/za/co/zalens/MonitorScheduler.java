package za.co.zalens;

import android.Manifest;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.pm.PackageManager;

/** Optional background work must never prevent the foreground app from opening. */
final class MonitorScheduler {
    static String schedule(Context context, Class<?> service) {
        try {
            // Android 14+ rejects network-constrained jobs without this normal permission.
            if(context.checkSelfPermission(Manifest.permission.ACCESS_NETWORK_STATE)!=PackageManager.PERMISSION_GRANTED)
                return "Background checks unavailable: network-state permission is missing.";
            JobScheduler scheduler=(JobScheduler)context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if(scheduler==null)return "Background checks unavailable: Android scheduler is not available.";
            JobInfo job=new JobInfo.Builder(202,new ComponentName(context,service))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(15*60*1000L).setPersisted(true).build();
            if(scheduler.schedule(job)!=JobScheduler.RESULT_SUCCESS)
                return "Background checks unavailable: Android declined the schedule. Reopen the app to retry.";
            return "";
        }catch(RuntimeException error){
            return "Background checks unavailable: "+error.getClass().getSimpleName()+". Reopen the app to retry.";
        }
    }
}
