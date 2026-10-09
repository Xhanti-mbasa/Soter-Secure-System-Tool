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
import org.json.JSONObject;
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
    private static final int SAVE_REPORT = 19;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setStatusBarColor(0xff0b1320);
        getWindow().setNavigationBarColor(0xff0b1320);
        prefs = getSharedPreferences("engine", MODE_PRIVATE);
        web = new WebView(this);
        web.setBackgroundColor(0xff0b1320);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new Bridge(), "Native");
        web.setWebViewClient(new WebViewClient() {
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
        setContentView(web);
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
        @JavascriptInterface public String config() {
            JSONObject result = new JSONObject();
            try { result.put("url", prefs.getString("url", "")); result.put("configured", !prefs.getString("url", "").isEmpty()); }
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
                    if (base.isEmpty()) throw new Exception("Connect your engine in Settings.");
                    conn=(HttpURLConnection)new URL(base+route).openConnection();
                    conn.setConnectTimeout(12000);conn.setReadTimeout(25000);
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
                    } else reply(id,result,"");
                } catch(Exception e) { reply(id,"",e.getMessage()); }
                finally { if(conn!=null) conn.disconnect(); }
            }});
        }
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
                pendingReport=text;
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
        if(request==SAVE_REPORT && result==RESULT_OK && data!=null && pendingReport!=null) {
            try {
                OutputStream out=getContentResolver().openOutputStream(data.getData());
                out.write(pendingReport.getBytes(StandardCharsets.UTF_8));out.close();
                Toast.makeText(this,"Research brief saved",Toast.LENGTH_SHORT).show();
            } catch(Exception e) { Toast.makeText(this,"Could not save report",Toast.LENGTH_LONG).show(); }
        }
        pendingReport=null;
    }
    @Override public void onBackPressed() {
        web.evaluateJavascript("(function(){var o=document.getElementById('overlay');if(o&&!o.hidden){window.closeDetail();return true;}return false;})()",new ValueCallback<String>() {
            @Override public void onReceiveValue(String value) { if(!"true".equals(value)) finish(); }
        });
    }
    @Override protected void onDestroy() {
        executor.shutdownNow();web.removeJavascriptInterface("Native");web.destroy();super.onDestroy();
    }
}
