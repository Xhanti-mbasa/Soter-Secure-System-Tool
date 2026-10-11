package za.co.zalens;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.ValueCallback;
import android.widget.Toast;
import android.webkit.WebChromeClient;
import android.location.Location;
import android.location.LocationManager;
import android.location.LocationListener;
import android.content.pm.PackageManager;
import android.provider.MediaStore;
import android.content.ClipData;
import android.util.Base64;
import java.util.UUID;
import org.json.JSONObject;
import org.json.JSONArray;
import android.Manifest;
import android.os.Build;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private WebView web;
    private SharedPreferences prefs;
    private final ExecutorService executor = Executors.newFixedThreadPool(2);
    private String pendingReport;
    private File pendingFile;
    private PublicServices services;
    private boolean monitoringScheduled;
    private static final int SAVE_REPORT = 19;
    private ValueCallback<Uri[]> fileCallback;
    private Uri captureUri;
    private String locationRequest;
    private LocationListener locationListener;
    private boolean keyboardVisible;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setStatusBarColor(0xff242424);
        getWindow().setNavigationBarColor(0xff242424);
        prefs = getSharedPreferences("engine", MODE_PRIVATE);
        services=new PublicServices(this);
        web = new WebView(this);
        web.setBackgroundColor(0xff242424);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new Bridge(), "Native");
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view,String url) {
                view.evaluateJavascript("window.sothisKeyboard && window.sothisKeyboard("+keyboardVisible+")",null);
                if(!monitoringScheduled && "file:///android_asset/index.html".equals(url)) {
                    monitoringScheduled=true;
                    String error=MonitorJob.schedule(MainActivity.this);
                    if(!error.isEmpty())Toast.makeText(MainActivity.this,"Background alerts unavailable. You can still use the app.",Toast.LENGTH_LONG).show();
                }
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.startsWith("file:///android_asset/")) return false;
                openExternal(url);
                return true;
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (url.startsWith("file:///android_asset/")) return false;
                openExternal(url);
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(fileCallback!=null)fileCallback.onReceiveValue(null);fileCallback=callback;captureUri=null;
                try{Intent pick=params.createIntent().putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);if(params.isCaptureEnabled()&&params.getAcceptTypes().length>0&&params.getAcceptTypes()[0].startsWith("image")){
                    File dir=new File(getCacheDir(),"capture");dir.mkdirs();String name=UUID.randomUUID().toString().replace("-","")+".jpg";captureUri=Uri.parse("content://za.co.zalens.files/capture/"+name);Intent camera=new Intent(MediaStore.ACTION_IMAGE_CAPTURE).putExtra(MediaStore.EXTRA_OUTPUT,captureUri).addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);camera.setClipData(ClipData.newRawUri("Photo",captureUri));if(camera.resolveActivity(getPackageManager())!=null)pick=camera;else captureUri=null;
                }else if(params.isCaptureEnabled()&&params.getAcceptTypes().length>0&&params.getAcceptTypes()[0].startsWith("video")){Intent camera=new Intent(MediaStore.ACTION_VIDEO_CAPTURE);if(camera.resolveActivity(getPackageManager())!=null)pick=camera;else captureUri=null;
                }else if(params.isCaptureEnabled()&&params.getAcceptTypes().length>0&&params.getAcceptTypes()[0].startsWith("audio")){Intent recorder=new Intent(MediaStore.Audio.Media.RECORD_SOUND_ACTION);if(recorder.resolveActivity(getPackageManager())!=null)pick=recorder;}
                startActivityForResult(pick,41);return true;}catch(Exception e){fileCallback.onReceiveValue(null);fileCallback=null;Toast.makeText(MainActivity.this,"No compatible picker available",Toast.LENGTH_LONG).show();return true;}
            }
        });
        setContentView(web);
        // adjustResize keeps fields above the IME; the dock must not follow it up.
        web.getViewTreeObserver().addOnGlobalLayoutListener(new android.view.ViewTreeObserver.OnGlobalLayoutListener() {
          @Override public void onGlobalLayout() {
            android.graphics.Rect visible = new android.graphics.Rect();
            web.getWindowVisibleDisplayFrame(visible);
            int obscured = web.getRootView().getHeight() - visible.bottom;
            boolean open = obscured > 120 * getResources().getDisplayMetrics().density;
            if (open != keyboardVisible) {
                keyboardVisible = open;
                web.evaluateJavascript("window.sothisKeyboard && window.sothisKeyboard("+open+")",null);
            }
          }
        });
        web.loadUrl("file:///android_asset/index.html");
    }

    private void openExternal(String value) {
        try {
            Uri uri = Uri.parse(value);
            if (!"https".equals(uri.getScheme()) && !"http".equals(uri.getScheme())) return;
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (Exception e) { Toast.makeText(this, "No browser available", Toast.LENGTH_SHORT).show(); }
    }

    private void reply(final String id, final String value, final String error) {
        runOnUiThread(new Runnable() { @Override public void run() {
            if (isDestroyed()) return;
            web.evaluateJavascript("window.nativeReply(" + JSONObject.quote(id) + "," +
                JSONObject.quote(value == null ? "" : value) + "," +
                JSONObject.quote(error == null ? "" : error) + ")", null);
        }});
    }

    private boolean localHost(String host) {
        if ("localhost".equals(host)) return true;
        if (host == null || !host.matches("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+")) return false;
        String[] parts = host.split("\\.");
        int[] n = new int[4];
        try { for (int i=0;i<4;i++) { n[i]=Integer.parseInt(parts[i]); if(n[i]>255) return false; } }
        catch (Exception e) { return false; }
        return n[0]==10 || n[0]==127 || (n[0]==192 && n[1]==168) ||
            (n[0]==172 && n[1]>=16 && n[1]<=31);
    }

    public final class Bridge {
        @JavascriptInterface public String dailyCapabilities(){return "news,opportunities,article,local-files,location,share-image";}
        @JavascriptInterface public String config() {
            JSONObject result = new JSONObject();
            try { result.put("url", prefs.getString("url", ""));result.put("launch_alerts",getIntent().getBooleanExtra("alerts",false)); result.put("configured", !prefs.getString("url", "").isEmpty()); result.put("search_key_configured",!getSharedPreferences("services",MODE_PRIVATE).getString("search_key","").isEmpty()); }
            catch (Exception ignored) {}
            return result.toString();
        }
        @JavascriptInterface public String snapshot() {
            try {
                InputStream in = getAssets().open("snapshot.json");
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] bytes = new byte[8192]; int count;
                while((count=in.read(bytes))!=-1) out.write(bytes,0,count);
                in.close();
                return new String(out.toByteArray(), StandardCharsets.UTF_8);
            } catch (Exception e) { return "{\"documents\":[],\"sources\":[]}"; }
        }
        @JavascriptInterface public String photoCredits() {
            try (InputStream in=getAssets().open("photo-credits.json")) {
                ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] bytes=new byte[4096];int count;
                while((count=in.read(bytes))!=-1)out.write(bytes,0,count);
                return new String(out.toByteArray(),StandardCharsets.UTF_8);
            } catch(Exception e) { return "[]"; }
        }
        @JavascriptInterface public String partySnapshot() {
            try { return PartyServices.snapshot(MainActivity.this); }
            catch(Exception e) { return "{\"parties\":[],\"profiles\":{},\"remuneration_schedules\":[]}"; }
        }
        @JavascriptInterface public String analyticsSnapshot() {
            try (InputStream in=getAssets().open("analytics-data.json")) {
                ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] bytes=new byte[8192];int count;
                while((count=in.read(bytes))!=-1)out.write(bytes,0,count);
                return new String(out.toByteArray(),StandardCharsets.UTF_8);
            } catch(Exception e) { return "{}"; }
        }
        @JavascriptInterface public String backgroundStatus() {
            return getSharedPreferences("services",MODE_PRIVATE).getString("background_error","");
        }
        @JavascriptInterface public String provinceSnapshot() {
            try{return ProvinceServices.asset(MainActivity.this,"province-data.json");}catch(Exception e){return "{}";}
        }
        @JavascriptInterface public String educationRegisters() {
            try{return ProvinceServices.asset(MainActivity.this,"education-registers.json");}catch(Exception e){return "{}";}
        }
        @JavascriptInterface public String configure(String value, String token) {
            try {
                value=value.trim().replaceAll("/+$", "");
                if (value.isEmpty()) { prefs.edit().remove("url").remove("token").apply(); return ""; }
                Uri u=Uri.parse(value);
                if (u.getHost()==null || u.getUserInfo()!=null || u.getQuery()!=null || u.getFragment()!=null)
                    return "Enter a valid engine URL without credentials or query parameters.";
                if (!"https".equals(u.getScheme()) && !("http".equals(u.getScheme()) && localHost(u.getHost())))
                    return "Use HTTPS, or HTTP with a private LAN IP address.";
                prefs.edit().putString("url",value).putString("token",token.trim()).apply();
                return "";
            } catch (Exception e) { return "Invalid engine URL"; }
        }
        @JavascriptInterface public void request(final String id, final String route, final String method, final String body) {
            executor.execute(new Runnable() { @Override public void run() {
                HttpURLConnection conn=null;
                try {
                    if (!route.startsWith("/api/") || route.contains("..") || route.contains("\\") ||
                        !("GET".equals(method) || "POST".equals(method))) throw new Exception("Invalid API request");
                    String base=prefs.getString("url", "");
                    if (base.isEmpty() || route.startsWith("/api/device/")) {
                        if(route.contains("/monitors"))getSharedPreferences("services",MODE_PRIVATE).edit().putString("monitor_backend","device").apply();
                        String result;
                        if(route.endsWith("/publication")||route.endsWith("/province/news")||route.startsWith("/api/device/daily/")||route.startsWith("/api/daily/"))result=services.execute(route.replace("/api/device/","/api/"),method,body);
                        else synchronized(PublicServices.class){result=services.execute(route.replace("/api/device/","/api/"),method,body);}
                        if(route.endsWith("/monitors/check"))MonitorJob.notifyAlerts(MainActivity.this,services.alerts());
                        reply(id,result,"");return;
                    }
                    conn=(HttpURLConnection)new URL(base+route).openConnection();
                    conn.setConnectTimeout(12000);conn.setReadTimeout(route.equals("/api/health")?15000:160000);
                    conn.setInstanceFollowRedirects(false);
                    conn.setRequestMethod(method);
                    String token=prefs.getString("token", "");
                    if (!token.isEmpty()) conn.setRequestProperty("Authorization","Bearer "+token);
                    if ("POST".equals(method)) {
                        conn.setDoOutput(true);conn.setRequestProperty("Content-Type","application/json");
                        OutputStream out=conn.getOutputStream();out.write(body.getBytes(StandardCharsets.UTF_8));out.close();
                    }
                    int status=conn.getResponseCode();
                    InputStream in=status<400?conn.getInputStream():conn.getErrorStream();
                    if(in==null) throw new Exception("Engine HTTP "+status);
                    ByteArrayOutputStream out=new ByteArrayOutputStream();
                    byte[] bytes=new byte[8192];int count;
                    while((count=in.read(bytes))!=-1) { out.write(bytes,0,count); if(out.size()>8*1024*1024) throw new Exception("Response exceeds 8 MiB"); }
                    in.close();
                    String result=new String(out.toByteArray(),StandardCharsets.UTF_8);
                    if(status>=400 || status<200 || status>=300) {
                        String error="Engine HTTP "+status;
                        try { error=new JSONObject(result).optString("error",error); } catch(Exception ignored) {}
                        reply(id,"",error);
                    } else {if(route.equals("/api/monitors"))getSharedPreferences("services",MODE_PRIVATE).edit().putString("monitor_backend","engine").apply();reply(id,result,"");}
                } catch(Exception e) { reply(id,"",e.getMessage()); }
                finally { if(conn!=null) conn.disconnect(); }
            }});
        }
        @JavascriptInterface public String sha256(String text) {try{return PublicServices.hash(text.getBytes(StandardCharsets.UTF_8));}catch(Exception e){return "Hash unavailable";}}
        @JavascriptInterface public void searchKey(String key) {
            getSharedPreferences("services",MODE_PRIVATE).edit().putString("search_key",key.trim()).apply();
        }
        @JavascriptInterface public void notifications() {
            runOnUiThread(new Runnable(){public void run(){if(Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},23);MonitorJob.schedule(MainActivity.this);}});
        }
        @JavascriptInterface public void bundle(final String name,final String value) {
            executor.execute(new Runnable(){public void run(){try {
                JSONObject data=new JSONObject(value);File file=new File(getCacheDir(),"research-evidence.zip");
                try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(file))) {
                    zip.putNextEntry(new ZipEntry("brief.md"));zip.write(data.optString("report").getBytes(StandardCharsets.UTF_8));zip.closeEntry();
                    zip.putNextEntry(new ZipEntry("manifest.json"));zip.write(data.toString(2).getBytes(StandardCharsets.UTF_8));zip.closeEntry();
                    JSONArray evidence=data.optJSONArray("evidence");if(evidence!=null)for(int i=0;i<evidence.length();i++) {
                        JSONObject item=evidence.getJSONObject(i);String sha=item.optString("sha256");if(!sha.matches("[a-f0-9]{64}"))continue;File original=new File(getFilesDir(),"evidence/"+sha);if(!original.isFile())continue;
                        zip.putNextEntry(new ZipEntry("originals/"+sha+(item.optString("mime").equals("application/pdf")?".pdf":item.optString("mime").equals("text/html")?".html":".bin")));try(FileInputStream in=new FileInputStream(original)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)zip.write(b,0,n);}zip.closeEntry();
                    }
                }
                runOnUiThread(new Runnable(){public void run(){pendingFile=file;pendingReport=null;Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/zip").putExtra(Intent.EXTRA_TITLE,name.replaceAll("[^a-zA-Z0-9._-]","_"));startActivityForResult(intent,SAVE_REPORT);}});
            }catch(Exception e){runOnUiThread(new Runnable(){public void run(){Toast.makeText(MainActivity.this,"Could not prepare evidence bundle",Toast.LENGTH_LONG).show();}});}}});
        }
        @JavascriptInterface public void binaryFile(final String name,final String base64,final String mime,final boolean sharing){
            executor.execute(new Runnable(){public void run(){try{
                if(base64.length()>28*1024*1024)throw new Exception("File too large");byte[] bytes=Base64.decode(base64,Base64.DEFAULT);if(bytes.length>20*1024*1024)throw new Exception("File too large");String ext=name.toLowerCase().matches(".*\\.(png|jpg|pdf|txt|eml|docx)$")?name.substring(name.lastIndexOf('.')+1).toLowerCase():"bin";File dir=new File(getCacheDir(),"share");dir.mkdirs();for(File old:dir.listFiles())if(System.currentTimeMillis()-old.lastModified()>24*3600000L)old.delete();final File file=new File(dir,UUID.randomUUID().toString().replace("-","")+"."+ext);try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}runOnUiThread(new Runnable(){public void run(){try{if(sharing){Uri uri=Uri.parse("content://za.co.zalens.files/share/"+file.getName());Intent intent=new Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(ClipData.newRawUri("Sothis card",uri));startActivity(Intent.createChooser(intent,"Share Sothis card"));}else{pendingFile=file;pendingReport=null;startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,name.replaceAll("[^a-zA-Z0-9._-]","_")),SAVE_REPORT);}}catch(Exception e){Toast.makeText(MainActivity.this,"No compatible app available",Toast.LENGTH_LONG).show();}}});
            }catch(Exception e){runOnUiThread(new Runnable(){public void run(){Toast.makeText(MainActivity.this,"Could not prepare the local file",Toast.LENGTH_LONG).show();}});}}});
        }
        @JavascriptInterface public void openEvidence(final String sha,final String mime){runOnUiThread(new Runnable(){public void run(){try{if(!sha.matches("[a-f0-9]{64}"))return;String ext=mime.equals("application/pdf")?"pdf":mime.startsWith("text/")?"txt":"bin";Uri uri=Uri.parse("content://za.co.zalens.files/evidence/"+sha+"."+ext);startActivity(new Intent(Intent.ACTION_VIEW).setDataAndType(uri,mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));}catch(Exception e){Toast.makeText(MainActivity.this,"No offline viewer available",Toast.LENGTH_LONG).show();}}});}
        @JavascriptInterface public void email(final String to,final String subject,final String body){runOnUiThread(new Runnable(){public void run(){try{if(!to.matches("[^\\s@]+@[^\\s@]+\\.[^\\s@]+"))return;startActivity(new Intent(Intent.ACTION_SENDTO,Uri.parse("mailto:"+Uri.encode(to))).putExtra(Intent.EXTRA_SUBJECT,subject).putExtra(Intent.EXTRA_TEXT,body));}catch(Exception e){Toast.makeText(MainActivity.this,"No email app available. Export the draft instead.",Toast.LENGTH_LONG).show();}}});}
        @JavascriptInterface public void notificationPreferences(String start,String end){if(start.matches("[0-2][0-9]:[0-5][0-9]")&&end.matches("[0-2][0-9]:[0-5][0-9]"))getSharedPreferences("services",MODE_PRIVATE).edit().putString("quiet_start",start).putString("quiet_end",end).apply();}
        @JavascriptInterface public void location(final String id){runOnUiThread(new Runnable(){public void run(){locationRequest=id;if(checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.ACCESS_COARSE_LOCATION,Manifest.permission.ACCESS_FINE_LOCATION},42);return;}requestProvinceLocation(id);}});}
        @JavascriptInterface public void open(final String url) {
            runOnUiThread(new Runnable() { @Override public void run() { openExternal(url); }});
        }
        @JavascriptInterface public void share(final String text) {
            runOnUiThread(new Runnable() { @Override public void run() {
                Intent intent=new Intent(Intent.ACTION_SEND);intent.setType("text/plain");
                intent.putExtra(Intent.EXTRA_TEXT,text);
                startActivity(Intent.createChooser(intent,"Share research brief"));
            }});
        }
        @JavascriptInterface public void save(final String name,final String text,final String mime) {
            runOnUiThread(new Runnable() { @Override public void run() {
                pendingReport=text;pendingFile=null;
                Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType(mime);
                intent.putExtra(Intent.EXTRA_TITLE,name.replaceAll("[^a-zA-Z0-9._-]","_"));
                try { startActivityForResult(intent,SAVE_REPORT); }
                catch(Exception e) { Toast.makeText(MainActivity.this,"No file picker available",Toast.LENGTH_LONG).show(); }
            }});
        }
    }

    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request==41){if(fileCallback!=null){Uri[] uris=result==RESULT_OK?(captureUri!=null?new Uri[]{captureUri}:pickerResult(result,data)):null;fileCallback.onReceiveValue(uris);fileCallback=null;captureUri=null;}return;}
        if(request==SAVE_REPORT && result==RESULT_OK && data!=null && (pendingReport!=null||pendingFile!=null)) {
            try {
                OutputStream out=getContentResolver().openOutputStream(data.getData());
                if(pendingFile!=null){try(FileInputStream in=new FileInputStream(pendingFile)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}}else out.write(pendingReport.getBytes(StandardCharsets.UTF_8));out.close();
                Toast.makeText(this,"Research brief saved",Toast.LENGTH_SHORT).show();
            } catch(Exception e) { Toast.makeText(this,"Could not save report",Toast.LENGTH_LONG).show(); }
        }
        pendingReport=null;pendingFile=null;
    }
    private Uri[] pickerResult(int result,Intent data){if(result!=RESULT_OK||data==null)return null;if(data.getClipData()!=null){ClipData clip=data.getClipData();Uri[] uris=new Uri[clip.getItemCount()];for(int i=0;i<uris.length;i++)uris[i]=clip.getItemAt(i).getUri();return uris;}return WebChromeClient.FileChooserParams.parseResult(result,data);}
    private void requestProvinceLocation(final String id){
        final LocationManager manager=(LocationManager)getSystemService(LOCATION_SERVICE);if(manager==null){reply(id,"","Location unavailable");return;}
        try{if(locationListener!=null)manager.removeUpdates(locationListener);locationListener=new LocationListener(){public void onLocationChanged(Location loc){try{JSONObject value=new JSONObject().put("latitude",loc.getLatitude()).put("longitude",loc.getLongitude());reply(id,value.toString(),"");manager.removeUpdates(this);locationListener=null;}catch(Exception e){reply(id,"","Location unavailable");}}public void onStatusChanged(String p,int s,Bundle b){}public void onProviderEnabled(String p){}public void onProviderDisabled(String p){}};
            String provider=manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)?LocationManager.NETWORK_PROVIDER:LocationManager.GPS_PROVIDER;if(!manager.isProviderEnabled(provider)){reply(id,"","Enable location or choose a province manually");return;}manager.requestSingleUpdate(provider,locationListener,getMainLooper());web.postDelayed(new Runnable(){public void run(){if(locationListener!=null&&id.equals(locationRequest)){manager.removeUpdates(locationListener);locationListener=null;reply(id,"","Location timed out; choose manually");}}},25000);
        }catch(Exception e){reply(id,"","Location unavailable; choose manually");}
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==42){if(checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED)requestProvinceLocation(locationRequest);else reply(locationRequest,"","Location permission declined; choose manually");}}
    @Override public void onBackPressed() {
        if(web==null){finish();return;}
        web.evaluateJavascript("(function(){if(typeof window.sothisBack==='function')return window.sothisBack();var o=document.getElementById('overlay');if(o&&!o.hidden){window.closeDetail();return true;}return false;})()",new ValueCallback<String>() {
            @Override public void onReceiveValue(String value) { if(!"true".equals(value)) finish(); }
        });
    }
    @Override protected void onDestroy() {
        if(locationListener!=null){((LocationManager)getSystemService(LOCATION_SERVICE)).removeUpdates(locationListener);locationListener=null;}
        executor.shutdownNow();if(web!=null){web.removeJavascriptInterface("Native");web.destroy();}super.onDestroy();
    }
}
