package za.co.zalens;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.Window;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.ValueCallback;
import android.widget.Toast;
import android.widget.FrameLayout;
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
    private final ExecutorService fileExecutor = Executors.newSingleThreadExecutor();
    private File pendingFile;
    private String pendingExportName="";
    private String pendingExportId="";
    private Uri pendingExportDestination;
    private int pendingExportGrantFlags;
    private boolean exportBusy;
    private boolean appVisible;
    private boolean pageLoaded;
    private boolean pendingAlertLaunch;
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
        if(state!=null&&state.containsKey("pending_export_path")) {
            try {
                String savedPath=state.getString("pending_export_path");
                boolean finished=LocalExports.isFinished(getCacheDir(),savedPath);
                if(!finished){
                    pendingFile=LocalExports.restore(getCacheDir(),savedPath);
                    pendingExportName=LocalExports.displayName(state.getString("pending_export_name"));
                }
                String destination=state.getString("pending_export_destination","");
                if(!destination.isEmpty()) {
                    Uri restored=Uri.parse(destination);
                    if(!"content".equals(restored.getScheme()))throw new Exception("Invalid save destination");
                    pendingExportDestination=restored;
                    pendingExportGrantFlags=state.getInt("pending_export_grant_flags",0);
                }
                // A recreated WebView has a new pending-request map. Never reuse its old id.
                if(finished)clearPendingExport();else exportBusy=true;
            } catch(Exception error) {
                pendingFile=null;pendingExportDestination=null;
                Toast.makeText(this,"Pending export unavailable. Prepare it again.",Toast.LENGTH_LONG).show();
            }
        }
        final File retainedExport=pendingFile;
        fileExecutor.execute(new Runnable(){public void run(){try {LocalExports.cleanup(getCacheDir(),retainedExport);}catch(Exception ignored){}}});
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
                pageLoaded=true;
                view.evaluateJavascript("window.sothisKeyboard && window.sothisKeyboard("+keyboardVisible+")",null);
                signalVisibility();
                if(pendingAlertLaunch){pendingAlertLaunch=false;openAlertInbox();}
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
        final FrameLayout content=new FrameLayout(this);
        content.setBackgroundColor(0xff242424);
        content.addView(web,new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT,FrameLayout.LayoutParams.MATCH_PARENT));
        if(Build.VERSION.SDK_INT>=30){
            // Keep web content inside system bars, cutouts and the IME under enforced edge-to-edge.
            getWindow().setDecorFitsSystemWindows(false);
            content.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener(){
                @Override public WindowInsets onApplyWindowInsets(View view,WindowInsets insets){
                    android.graphics.Insets system=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
                    android.graphics.Insets ime=insets.getInsets(WindowInsets.Type.ime());
                    view.setPadding(system.left,system.top,system.right,Math.max(system.bottom,ime.bottom));
                    updateKeyboardVisible(insets.isVisible(WindowInsets.Type.ime()));
                    // The wrapper owns these insets; do not apply them a second time inside WebView.
                    return WindowInsets.CONSUMED;
                }
            });
        }else{
            // API 26-29 keep adjustResize and the visible-display keyboard detector.
            web.getViewTreeObserver().addOnGlobalLayoutListener(new android.view.ViewTreeObserver.OnGlobalLayoutListener(){
                @Override public void onGlobalLayout(){
                    android.graphics.Rect visible=new android.graphics.Rect();
                    web.getWindowVisibleDisplayFrame(visible);
                    int obscured=web.getRootView().getHeight()-visible.bottom;
                    updateKeyboardVisible(obscured>120*getResources().getDisplayMetrics().density);
                }
            });
        }
        setContentView(content);
        if(Build.VERSION.SDK_INT>=30)content.requestApplyInsets();
        web.loadUrl("file:///android_asset/index.html");
        if(pendingFile!=null&&pendingExportDestination!=null)writePendingExport();
    }

    private void updateKeyboardVisible(boolean visible){
        if(visible==keyboardVisible)return;
        keyboardVisible=visible;
        if(web!=null)web.evaluateJavascript("window.sothisKeyboard && window.sothisKeyboard("+visible+")",null);
    }

    private boolean activityAvailable(){return !isFinishing()&&!isDestroyed();}
    private void signalVisibility(){
        if(web!=null)web.evaluateJavascript("window.sothisAppVisibility && window.sothisAppVisibility("+appVisible+")",null);
    }
    private void openAlertInbox(){
        if(web!=null)web.evaluateJavascript("if(typeof window.openAlertInbox==='function')window.openAlertInbox();",null);
    }
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);setIntent(intent);
        if(intent.getBooleanExtra("alerts",false)){if(pageLoaded)openAlertInbox();else pendingAlertLaunch=true;}
    }
    @Override protected void onPause(){
        appVisible=false;signalVisibility();if(web!=null)web.onPause();super.onPause();
    }
    @Override protected void onResume(){
        super.onResume();appVisible=true;if(web!=null)web.onResume();signalVisibility();
    }
    @Override protected void onSaveInstanceState(Bundle state){
        if(pendingFile!=null){
            try {
                File file=LocalExports.restore(getCacheDir(),pendingFile.getPath());
                state.putString("pending_export_path",file.getPath());
                state.putString("pending_export_name",pendingExportName);
                if(pendingExportDestination!=null)state.putString("pending_export_destination",pendingExportDestination.toString());
                if(pendingExportGrantFlags!=0)state.putInt("pending_export_grant_flags",pendingExportGrantFlags);
            }catch(Exception ignored){/* Missing cache files must not prevent state saving. */}
        }
        super.onSaveInstanceState(state);
    }

    private interface ExportPreparation {File prepare()throws Exception;}
    private void clearPendingExport(){
        if(pendingExportDestination!=null&&pendingExportGrantFlags!=0){
            try {getContentResolver().releasePersistableUriPermission(pendingExportDestination,pendingExportGrantFlags);}catch(SecurityException ignored){}
        }
        pendingFile=null;pendingExportName="";pendingExportId="";pendingExportDestination=null;pendingExportGrantFlags=0;exportBusy=false;
    }
    private void exportResult(String id,String status,String name){
        if(!activityAvailable())return;
        if(id!=null&&!id.isEmpty()) {
            try {reply(id,new JSONObject().put("status",status).put("name",name).toString(),"");}
            catch(Exception error){reply(id,"","Could not report the export result");}
        } else if("saved".equals(status))Toast.makeText(this,"File saved",Toast.LENGTH_SHORT).show();
    }
    private void exportFailure(String id,String message){
        if(!activityAvailable())return;
        File staged=pendingFile;clearPendingExport();if(staged!=null)staged.delete();
        String detail=message==null||message.isEmpty()?"Could not export the file":message;
        if(id!=null&&!id.isEmpty())reply(id,"",detail);
        else Toast.makeText(this,detail,Toast.LENGTH_LONG).show();
    }
    private void beginExport(final String id,final String name,final String mime,final boolean sharing,final ExportPreparation preparation){
        runOnUiThread(new Runnable(){public void run(){
            if(!activityAvailable())return;
            if(exportBusy){
                if(id!=null&&!id.isEmpty())reply(id,"","Finish or cancel the current export first");
                else Toast.makeText(MainActivity.this,"Finish or cancel the current export first",Toast.LENGTH_LONG).show();
                return;
            }
            exportBusy=true;pendingExportId=id==null?"":id;
            try {fileExecutor.execute(new Runnable(){public void run(){
                try {
                    LocalExports.cleanup(getCacheDir(),pendingFile);
                    final File file=preparation.prepare();
                    runOnUiThread(new Runnable(){public void run(){
                        if(!activityAvailable()){file.delete();return;}
                        try {
                            if(sharing){
                                Uri uri=Uri.parse("content://za.co.zalens.files/share/"+file.getName());
                                Intent intent=new Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                                intent.setClipData(ClipData.newRawUri(LocalExports.displayName(name),uri));
                                startActivity(Intent.createChooser(intent,"Share Sothis file"));
                                clearPendingExport();exportResult(id,"handoff",LocalExports.displayName(name));
                            }else{
                                pendingFile=LocalExports.restore(getCacheDir(),file.getPath());
                                pendingExportName=LocalExports.displayName(name);
                                startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,pendingExportName),SAVE_REPORT);
                            }
                        }catch(Exception error){file.delete();exportFailure(id,"No compatible save or sharing app available");}
                    }});
                }catch(final Exception error){runOnUiThread(new Runnable(){public void run(){exportFailure(id,error.getMessage());}});}
            }});}catch(Exception error){exportFailure(id,"Export preparation is unavailable. Reopen the app and retry.");}
        }});
    }
    private void writePendingExport(){
        final File file=pendingFile;final Uri destination=pendingExportDestination;
        final String id=pendingExportId,name=pendingExportName;
        if(file==null||destination==null){exportFailure(id,"Pending export unavailable. Prepare it again.");return;}
        try {fileExecutor.execute(new Runnable(){public void run(){
            String failure="";
            try {
                File validated=LocalExports.restore(getCacheDir(),file.getPath());
                if(!LocalExports.isFinished(getCacheDir(),validated.getPath())){
                    LocalExports.write(validated,new LocalExports.Destination(){public OutputStream open()throws java.io.IOException{return getContentResolver().openOutputStream(destination,"wt");}});
                    LocalExports.markFinished(getCacheDir(),validated);
                }
            }catch(Exception error){failure=error.getMessage()==null?"The selected destination could not be written":error.getMessage();}
            final String error=failure;
            runOnUiThread(new Runnable(){public void run(){
                if(!activityAvailable())return;
                if(!error.isEmpty()){exportFailure(id,error);return;}
                clearPendingExport();file.delete();exportResult(id,"saved",name);
            }});
        }});}catch(Exception error){exportFailure(id,"Export writing is unavailable. Reopen the app and retry.");}
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
                        String result,normalized=route.replace("/api/device/","/api/"),localPath=normalized.split("\\?",2)[0];
                        if(localPath.startsWith("/api/monitors")||localPath.equals("/api/alerts")){
                            synchronized(PublicServices.MONITOR_LOCK){result=services.execute(normalized,method,body);}
                        }else result=services.execute(normalized,method,body);
                        if(localPath.equals("/api/monitors/check")){
                            JSONArray alerts;synchronized(PublicServices.MONITOR_LOCK){alerts=services.alerts();}
                            MonitorJob.notifyAlerts(MainActivity.this,alerts);
                        }
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
            beginExport("",name,"application/zip",false,new ExportPreparation(){public File prepare()throws Exception{
                JSONObject data=new JSONObject(value);File file=LocalExports.newFile(getCacheDir(),"exports","research-evidence.zip");
                try {
                try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(file))) {
                    zip.putNextEntry(new ZipEntry("brief.md"));zip.write(data.optString("report").getBytes(StandardCharsets.UTF_8));zip.closeEntry();
                    zip.putNextEntry(new ZipEntry("manifest.json"));zip.write(data.toString(2).getBytes(StandardCharsets.UTF_8));zip.closeEntry();
                    JSONArray evidence=data.optJSONArray("evidence");if(evidence!=null)for(int i=0;i<evidence.length();i++) {
                        JSONObject item=evidence.getJSONObject(i);String sha=item.optString("sha256");if(!sha.matches("[a-f0-9]{64}"))continue;File original=new File(getFilesDir(),"evidence/"+sha);if(!original.isFile())continue;
                        zip.putNextEntry(new ZipEntry("originals/"+sha+(item.optString("mime").equals("application/pdf")?".pdf":item.optString("mime").equals("text/html")?".html":".bin")));try(FileInputStream in=new FileInputStream(original)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)zip.write(b,0,n);}zip.closeEntry();
                    }
                }
                return file;
                }catch(Exception error){file.delete();throw error;}
            }});
        }
        @JavascriptInterface public void binaryFile(final String name,final String base64,final String mime,final boolean sharing){
            exportFile("",name,base64,mime,sharing);
        }
        @JavascriptInterface public void exportFile(final String id,final String name,final String base64,final String mime,final boolean sharing){
            beginExport(id,name,mime,sharing,new ExportPreparation(){public File prepare()throws Exception{
                if(base64==null||base64.length()>28*1024*1024)throw new Exception("File limit is 20 MiB");
                byte[] bytes=Base64.decode(base64,Base64.DEFAULT);
                return LocalExports.stage(getCacheDir(),sharing?"share":"exports",name,bytes);
            }});
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
            beginExport("",name,mime,false,new ExportPreparation(){public File prepare()throws Exception{return LocalExports.stageText(getCacheDir(),name,text);}});
        }
    }

    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request==41){if(fileCallback!=null){Uri[] uris=result==RESULT_OK?(captureUri!=null?new Uri[]{captureUri}:pickerResult(result,data)):null;fileCallback.onReceiveValue(uris);fileCallback=null;captureUri=null;}return;}
        if(request==SAVE_REPORT){
            if(result!=RESULT_OK){
                final String id=pendingExportId,name=pendingExportName;final File file=pendingFile;
                try {fileExecutor.execute(new Runnable(){public void run(){
                    try {if(file!=null)LocalExports.markFinished(getCacheDir(),file);}
                    catch(Exception ignored){/* The cancelled picker has never written a destination. */}
                    runOnUiThread(new Runnable(){public void run(){if(!activityAvailable())return;clearPendingExport();if(file!=null)file.delete();exportResult(id,"cancelled",name);}});
                }});}catch(Exception error){exportFailure(id,"Could not clear the pending export. Reopen the app.");}
                return;
            }
            Uri uri=data==null?null:data.getData();
            if(uri==null||!"content".equals(uri.getScheme())){exportFailure(pendingExportId,"The selected save destination is unavailable");return;}
            int flags=data.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            if((data.getFlags()&Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)!=0&&flags!=0){
                try {getContentResolver().takePersistableUriPermission(uri,flags);pendingExportGrantFlags=flags;}
                catch(SecurityException ignored){/* The current temporary grant still permits this save. */}
            }
            pendingExportDestination=uri;writePendingExport();
        }
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
        if(locationListener!=null){LocationManager manager=(LocationManager)getSystemService(LOCATION_SERVICE);if(manager!=null)manager.removeUpdates(locationListener);locationListener=null;}
        if(fileCallback!=null){fileCallback.onReceiveValue(null);fileCallback=null;}
        executor.shutdownNow();fileExecutor.shutdownNow();if(web!=null){web.removeJavascriptInterface("Native");web.destroy();}super.onDestroy();
    }
}
