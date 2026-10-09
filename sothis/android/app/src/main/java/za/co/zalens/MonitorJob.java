package za.co.zalens;
import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.*;
import android.content.Context;
import android.content.Intent;
import android.content.ComponentName;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** JobScheduler resumes after reboot; Android may defer checks for battery/network. */
public final class MonitorJob extends JobService {
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private Future<?> task;
    static void schedule(Context c) {
        JobScheduler scheduler=(JobScheduler)c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        scheduler.schedule(new JobInfo.Builder(202,new ComponentName(c,MonitorJob.class))
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(15*60*1000L).setPersisted(true).build());
    }
    static void notifyAlerts(Context c,JSONArray alerts) throws Exception {
        NotificationManager manager=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
        manager.createNotificationChannel(new NotificationChannel("monitoring","Sothis monitoring",NotificationManager.IMPORTANCE_DEFAULT));
        if(Build.VERSION.SDK_INT>=33&&c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return;
        SharedPreferences prefs=c.getSharedPreferences("notifications",Context.MODE_PRIVATE);
        Set<String> delivered=new HashSet<>(prefs.getStringSet("delivered",new HashSet<String>()));
        for(int i=0;i<alerts.length();i++) {
            JSONObject a=alerts.getJSONObject(i);String id=a.getString("id");if(delivered.contains(id)||a.optBoolean("read"))continue;
            Intent open=new Intent(c,MainActivity.class).putExtra("alerts",true);
            PendingIntent pending=PendingIntent.getActivity(c,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
            manager.notify(id.hashCode(),new Notification.Builder(c,"monitoring").setSmallIcon(android.R.drawable.ic_popup_reminder).setContentTitle("New evidence: "+a.optString("query"))
                .setContentText(a.optString("service")+" · "+a.optJSONObject("hit").optString("title","New matching result")).setContentIntent(pending).setAutoCancel(true).build());delivered.add(id);
        }
        prefs.edit().putStringSet("delivered",delivered).apply();
    }
    @Override public boolean onStartJob(final JobParameters parameters) {
        task=worker.submit(new Runnable(){public void run(){
            try {
                SharedPreferences engine=getSharedPreferences("engine",MODE_PRIVATE);String base=engine.getString("url","");JSONArray inbox;
                if(!base.isEmpty()&&getSharedPreferences("services",MODE_PRIVATE).getString("monitor_backend","engine").equals("engine"))inbox=new JSONArray(new String(PublicServices.fetch(base+"/api/alerts",8*1024*1024,false,engine.getString("token","")),StandardCharsets.UTF_8));
                else {PublicServices services=new PublicServices(MonitorJob.this);JSONArray rules=services.rules();for(int i=0;i<rules.length();i++){JSONObject r=rules.getJSONObject(i);if(r.optBoolean("enabled",true)&&System.currentTimeMillis()-r.optLong("last_checked_ms",0)>=r.optInt("interval_minutes",120)*60000L){synchronized(PublicServices.class){services.check(r.getString("id"));}}}inbox=services.alerts();}
                notifyAlerts(MonitorJob.this,inbox);
            }catch(Exception ignored){}finally{jobFinished(parameters,false);}
        }});return true;
    }
    @Override public boolean onStopJob(JobParameters p){if(task!=null)task.cancel(true);return true;}
    @Override public void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
