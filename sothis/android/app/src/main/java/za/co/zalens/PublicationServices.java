package za.co.zalens;

import org.json.JSONArray;
import org.json.JSONObject;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.*;
import java.util.regex.*;

/** Explicit source publication metadata; search page age may be a modified date. */
public final class PublicationServices {
    private final LinkedHashMap<String,String> dates=new LinkedHashMap<>();
    private void add(String value,String label) {
        try { if(value.length()>=10)dates.put(LocalDate.parse(value.substring(0,10)).toString(),label); }
        catch(Exception invalid) { /* Unknown date formats remain unavailable. */ }
    }
    private void structured(Object node) throws Exception {
        if(node instanceof JSONArray) {JSONArray a=(JSONArray)node;for(int i=0;i<a.length();i++)structured(a.get(i));}
        else if(node instanceof JSONObject) {
            JSONObject o=(JSONObject)node;Object type=o.opt("@type");List<String> types=new ArrayList<>();
            if(type instanceof String)types.add((String)type);
            else if(type instanceof JSONArray)for(int i=0;i<((JSONArray)type).length();i++)types.add(((JSONArray)type).optString(i));
            for(String t:types)if(Arrays.asList("Article","NewsArticle","BlogPosting","Report","WebPage").contains(t)){add(o.optString("datePublished"),"Source structured data · datePublished");break;}
            Iterator<String> keys=o.keys();while(keys.hasNext()){Object n=o.get(keys.next());if(n instanceof JSONObject||n instanceof JSONArray)structured(n);}
        }
    }
    private static Map<String,String> attributes(String tag) {
        Map<String,String> attrs=new HashMap<>();Matcher m=Pattern.compile("([\\w:-]+)\\s*=\\s*([\"'])(.*?)\\2",Pattern.DOTALL).matcher(tag);
        while(m.find())attrs.put(m.group(1).toLowerCase(Locale.US),PublicServices.clean(m.group(3)));return attrs;
    }
    JSONObject parse(String html) throws Exception {
        Matcher tags=Pattern.compile("<(?:meta|time)\\b[^>]*>",Pattern.CASE_INSENSITIVE).matcher(html);
        while(tags.find()) {
            Map<String,String> a=attributes(tags.group());String key=a.containsKey("property")?a.get("property"):a.get("name");
            if(key!=null&&Arrays.asList("article:published_time","datepublished","pubdate").contains(key.toLowerCase(Locale.US)))add(a.getOrDefault("content",""),"Source metadata · "+key);
            if("datePublished".equalsIgnoreCase(a.get("itemprop")))add(a.containsKey("content")?a.get("content"):a.getOrDefault("datetime",""),"Source metadata · datePublished");
        }
        Matcher scripts=Pattern.compile("<script\\b([^>]*)>(.*?)</script>",Pattern.DOTALL|Pattern.CASE_INSENSITIVE).matcher(html);
        while(scripts.find())if("application/ld+json".equalsIgnoreCase(attributes(scripts.group(1)).get("type")))try {
            String json=scripts.group(2).trim();structured(json.startsWith("[")?new JSONArray(json):new JSONObject(json));
        }catch(Exception malformed){ /* A malformed structured block is not date evidence. */ }
        JSONObject r=new JSONObject().put("published_at",JSONObject.NULL).put("publication_date_source",JSONObject.NULL).put("date_status",dates.size()>1?"conflicting_metadata":"not_published");
        if(dates.size()==1){String date=dates.keySet().iterator().next();r.put("published_at",date).put("publication_date_source",dates.get(date)).put("date_status","explicit_metadata");}
        return r;
    }
    public static JSONObject publication(String address) throws Exception {
        URI u=new URI(address);if(!"https".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null||(u.getPort()!=-1&&u.getPort()!=443))throw new java.io.IOException("Use a public HTTPS article URL");
        byte[] raw=PublicServices.fetch(address,2*1024*1024,true,null);
        String html=new String(raw,StandardCharsets.UTF_8);
        if(!html.trim().startsWith("<"))throw new java.io.IOException("Article metadata requires an HTML source");
        return new PublicationServices().parse(html).put("publication_source_url",address).put("publication_content_hash",PublicServices.hash(raw)).put("date_checked_at",PublicServices.stamp());
    }
}
