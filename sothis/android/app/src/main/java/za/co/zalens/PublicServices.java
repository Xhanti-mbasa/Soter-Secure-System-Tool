package za.co.zalens;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.Html;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.regex.*;

/** Native public adapters work without a hosted engine. No platform login scraping. */
public final class PublicServices {
    static final String PORTAL="https://www.etenders.gov.za/Home/opportunities";
    private final Context context;
    private final SharedPreferences prefs;
    public PublicServices(Context context) { this.context=context; prefs=context.getSharedPreferences("services",Context.MODE_PRIVATE); }
    public static String stamp() { SimpleDateFormat f=new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'",Locale.US);f.setTimeZone(TimeZone.getTimeZone("UTC"));return f.format(new Date()); }
    public static String hash(byte[] bytes) throws Exception { StringBuilder s=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))s.append(String.format(Locale.US,"%02x",b&255));return s.toString(); }
    static String hash(String text) throws Exception { return hash(text.getBytes(StandardCharsets.UTF_8)); }
    static String clean(String text) { return Html.fromHtml(text,Html.FROM_HTML_MODE_LEGACY).toString().replaceAll("\\s+"," ").trim(); }
    static String enc(String text) throws Exception { return URLEncoder.encode(text,"UTF-8"); }
    static String registration(String value) { String s=value.replaceAll("[\\s/\\-]","");return s.matches("(?:19|20)\\d{10}")?s.substring(0,4)+"/"+s.substring(4,10)+"/"+s.substring(10):""; }
    static byte[] fetch(String address, int maximum, boolean publicOnly, String token) throws Exception {
        String current=address;
        for(int redirect=0;redirect<5;redirect++) {
            URL url=new URL(current);
            if(!url.getProtocol().equals("https") && !(token!=null && url.getProtocol().equals("http")))throw new IOException("HTTPS required for public sources");
            if(url.getUserInfo()!=null)throw new IOException("URL credentials are not accepted");
            if(publicOnly)for(InetAddress ip:InetAddress.getAllByName(url.getHost())) {
                if(ip.isAnyLocalAddress()||ip.isLoopbackAddress()||ip.isLinkLocalAddress()||ip.isSiteLocalAddress()||ip.isMulticastAddress()||ip.getHostAddress().startsWith("fc")||ip.getHostAddress().startsWith("fd"))throw new IOException("Private network URLs cannot be archived");
            }
            HttpURLConnection c=(HttpURLConnection)url.openConnection();c.setConnectTimeout(12000);c.setReadTimeout(18000);c.setInstanceFollowRedirects(false);
            c.setRequestProperty("User-Agent","Mozilla/5.0 (compatible; Sothis/0.2)");
            if(token!=null&&!token.isEmpty())c.setRequestProperty("Authorization","Bearer "+token);
            try {
                int status=c.getResponseCode();
                if(status>=300&&status<400) { if(token!=null)throw new IOException("Engine redirect refused");String location=c.getHeaderField("Location");if(location==null)throw new IOException("Redirect without location");current=new URL(url,location).toString();continue; }
                if(status!=200)throw new IOException("Provider HTTP "+status+(status==429?". Rate limited; try later or use a Search API key.":""));
                ByteArrayOutputStream out=new ByteArrayOutputStream();try(InputStream in=c.getInputStream()) { byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>maximum)throw new IOException("Response exceeds size limit");} }
                return out.toByteArray();
            } finally { c.disconnect(); }
        }
        throw new IOException("Too many redirects");
    }
    static String read(String url) throws Exception { return new String(fetch(url,8*1024*1024,false,null),StandardCharsets.UTF_8); }
    static String platform(String address) throws Exception {
        URI u=new URI(address);String host=u.getHost().toLowerCase(Locale.US).replaceFirst("^(www\\.|m\\.)","");String path=u.getPath();if(path==null)path="";
        if(path.matches("(?i).*/(p|reel|reels|posts|post|status|statuses|video|videos|watch|discover|share|sharer|intent|search|hashtag|groups|login|accounts|stories|events)(/.*)?"))return "";
        if(path.matches("(?i).*/(?:share|sharer|intent)[^/]*(/.*)?"))return "";
        String[] parts=path.replaceAll("^/+|/+$","").split("/");
        if(host.equals("linkedin.com"))return parts.length==2&&parts[0].equals("in")?"LinkedIn":"";
        if(host.equals("tiktok.com"))return parts.length==1&&parts[0].startsWith("@")?"TikTok":"";
        if(host.equals("youtube.com"))return (parts.length==1&&parts[0].startsWith("@"))||(parts.length==2&&Arrays.asList("channel","c","user").contains(parts[0]))?"YouTube":"";
        if(host.equals("facebook.com")&&path.equals("/profile.php")&&u.getQuery()!=null&&u.getQuery().contains("id="))return "Facebook";
        if(parts.length!=1||parts[0].isEmpty()||Arrays.asList("home","explore","help","about","privacy","terms").contains(parts[0].toLowerCase(Locale.US)))return "";
        return host.equals("instagram.com")?"Instagram":host.equals("facebook.com")?"Facebook":host.equals("x.com")||host.equals("twitter.com")?"X / Twitter":"";
    }
    static JSONObject hit(String address,String title,String description,String query) throws Exception {
        URI u=new URI(address);if(u.getHost()==null||u.getUserInfo()!=null||!(u.getScheme().equals("https")||u.getScheme().equals("http")))return null;
        String path=u.getPath()==null?"/":u.getPath().replaceAll("/+$","");String url=new URI(u.getScheme(),u.getAuthority(),path.isEmpty()?"/":path,path.equals("/profile.php")?u.getQuery():null,null).toString();
        title=clean(title);description=clean(description);String hay=(title+" "+description+" "+URLDecoder.decode(url,"UTF-8")).toLowerCase(Locale.US);String reg=registration(query);
        if(!reg.isEmpty()) { if(!hay.replaceAll("\\D","").contains(reg.replaceAll("\\D","")))return null; }
        else for(String term:query.toLowerCase(Locale.US).split("[^\\p{L}\\p{N}_]+"))if(!term.isEmpty()&&!hay.contains(term))return null;
        String social=platform(url);boolean exact=(title+" "+description).toLowerCase(Locale.US).contains(query.toLowerCase(Locale.US));
        return new JSONObject().put("id",hash(url).substring(0,24)).put("url",url).put("title",title.isEmpty()?url:title).put("description",description)
            .put("platform",social.isEmpty()?JSONObject.NULL:social).put("category",!social.isEmpty()?"social":u.getHost().endsWith(".gov.za")?"government":"web")
            .put("match_score",(exact?90:65)+(social.isEmpty()?0:5)).put("match_label",exact?"Strong name match":"Name terms match")
            .put("match_reason","Text relevance, not proof of identity. Confirm account ownership yourself.").put("ownership","unreviewed").put("retrieved_at",stamp())
            .put("content_hash",hash(title+"\n"+description)).put("acquisition","search_index");
    }
    public JSONObject discover(String query,String scope,boolean fresh) throws Exception {
        return discover(query,scope,fresh,"");
    }
    public JSONObject discover(String query,String scope,boolean fresh,String topic) throws Exception {
        query=query.trim();if(query.length()<2||query.length()>160)throw new IOException("Enter 2–160 characters");
        if(!Arrays.asList("all","social","government","company").contains(scope))throw new IOException("Unsupported search scope");
        String topicTerms=topic.equals("education")?"(education OR university OR qualifications OR degree)":topic.equals("remuneration")?"(salary OR salaries OR remuneration)":topic.equals("news")?"news":"";
        if(!topic.isEmpty()&&topicTerms.isEmpty())throw new IOException("Unsupported discovery topic");
        String cacheKey="cache-"+hash(query.toLowerCase(Locale.US)+scope+topic);String cache=prefs.getString(cacheKey,"");
        if(!fresh&&!cache.isEmpty()&&System.currentTimeMillis()-prefs.getLong(cacheKey+"-time",0)<300000)return new JSONObject(cache).put("cached",true);
        String reg=registration(query),q=(reg.isEmpty()?query:reg).replace("\"","");
        String social="(site:instagram.com OR site:facebook.com OR site:linkedin.com/in OR site:x.com OR site:twitter.com OR site:tiktok.com/@ OR site:youtube.com/@)";
        List<String> queries=new ArrayList<>();queries.add(q+(scope.equals("social")?" "+social:scope.equals("government")?" (site:gov.za OR site:parliament.gov.za)":scope.equals("company")?" (company OR CIPC OR enterprise)":""));
        if(!topicTerms.isEmpty())queries.set(0,queries.get(0)+" "+topicTerms);
        // One public request per search avoids multiplying best-effort provider traffic.
        Map<String,JSONObject> hits=new LinkedHashMap<>();JSONArray statuses=new JSONArray();
        for(String search:queries) {
            try {
                String apiKey=prefs.getString("search_key","");String provider="Brave public search (best effort)";JSONArray rows=new JSONArray();
                if(!apiKey.isEmpty()) {
                    HttpURLConnection c=(HttpURLConnection)new URL("https://api.search.brave.com/res/v1/web/search?q="+enc(search)+"&count=20&country=ZA").openConnection();c.setConnectTimeout(12000);c.setReadTimeout(18000);c.setInstanceFollowRedirects(false);c.setRequestProperty("X-Subscription-Token",apiKey);
                    try { if(c.getResponseCode()!=200)throw new IOException("Search API HTTP "+c.getResponseCode());ByteArrayOutputStream out=new ByteArrayOutputStream();try(InputStream in=c.getInputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>8*1024*1024)throw new IOException("Response too large");}}rows=new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8)).optJSONObject("web")==null?new JSONArray():new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8)).getJSONObject("web").optJSONArray("results");if(rows==null)rows=new JSONArray(); }
                    finally {c.disconnect();}
                } else {
                    String html;try{html=read("https://search.brave.com/search?q="+enc(search)+"&source=web");}catch(Exception failed){html=read("https://lite.duckduckgo.com/lite/?q="+enc(search));provider="DuckDuckGo public search (best effort)";}

                    Matcher a=Pattern.compile("<a\\b([^>]+)>(.*?)</a>",Pattern.DOTALL|Pattern.CASE_INSENSITIVE).matcher(html);
                    while(a.find()) { String attrs=a.group(1);Matcher cls=Pattern.compile("class=\"([^\"]*)\"").matcher(attrs),href=Pattern.compile("href=\"([^\"]*)\"").matcher(attrs);if(!cls.find()||!(Arrays.asList(cls.group(1).split(" ")).contains("l1")||Arrays.asList(cls.group(1).split(" ")).contains("result-link"))||!href.find())continue;String body=a.group(2);Matcher t=Pattern.compile("<(?:div|span)[^>]*class=\"[^\"]*(?:snippet-title|title)[^\"]*\"[^>]*>(.*?)</(?:div|span)>",Pattern.DOTALL).matcher(body);String found=clean(href.group(1));if(found.startsWith("//duckduckgo.com/l/")){Matcher target=Pattern.compile("[?&]uddg=([^&]+)").matcher(found);found=target.find()?URLDecoder.decode(target.group(1),"UTF-8"):"";}rows.put(new JSONObject().put("url",found).put("title",t.find()?clean(t.group(1)):clean(body)).put("description",clean(body))); }
                    if(rows.length()==0&&html.toLowerCase(Locale.US).matches("(?s).*(captcha|verify you are human|too many requests).*"))throw new IOException("Provider needs a browser check. Open browser search or configure a Search API key.");
                }
                for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i),h=hit(row.optString("url"),row.optString("title"),row.optString("description"),reg.isEmpty()?query:reg);if(h!=null&&(!scope.equals("social")||!h.isNull("platform"))&&(!scope.equals("government")||h.optString("category").equals("government"))){h.put("published_at",JSONObject.NULL);String age=row.optString("page_age");try{if(age.length()>=10)h.put("index_date",java.time.LocalDate.parse(age.substring(0,10)).toString());}catch(Exception unknown){}JSONObject previous=hits.get(h.getString("url"));if(previous==null||h.optString("description").length()>previous.optString("description").length())hits.put(h.getString("url"),h);}}
                statuses.put(new JSONObject().put("service",apiKey.isEmpty()?provider:"Brave Search API").put("status","completed").put("retrieved",rows.length()));
            } catch(Exception e) { statuses.put(new JSONObject().put("service","Web discovery").put("status","unavailable").put("detail",e.getMessage())); }
        }
        JSONArray companies=new JSONArray();
        if(!reg.isEmpty())try {
            JSONArray raw=new JSONArray(read("https://www.etenders.gov.za/Home/GetCompanies?search="+enc(reg)));
            for(int i=0;i<raw.length()&&companies.length()<20;i++)if(raw.get(i).toString().replaceAll("\\D","").contains(reg.replaceAll("\\D","")))companies.put(new JSONObject().put("record",raw.get(i)).put("source_url",PORTAL).put("authority","eTenders supplier index; not a CIPC certificate"));
            statuses.put(new JSONObject().put("service","eTenders supplier index").put("status","completed").put("retrieved",companies.length()));
        } catch(Exception e) {statuses.put(new JSONObject().put("service","eTenders supplier index").put("status","unavailable").put("detail",e.getMessage()));}
        List<JSONObject> sorted=new ArrayList<>(hits.values());Collections.sort(sorted,new Comparator<JSONObject>(){public int compare(JSONObject a,JSONObject b){return b.optInt("match_score")-a.optInt("match_score");}});JSONArray results=new JSONArray();int accounts=0;for(JSONObject h:sorted){results.put(h);if(!h.isNull("platform"))accounts++;}
        JSONObject result=new JSONObject().put("query",query).put("topic",topic).put("registration_number",reg.isEmpty()?JSONObject.NULL:reg).put("results",results).put("hit_count",results.length()).put("account_count",accounts).put("companies",companies).put("statuses",statuses).put("retrieved_at",stamp()).put("cached",false)
            .put("cipc",new JSONObject().put("status","authorised_access_required").put("url","https://www.bizportal.gov.za/").put("detail","BizProfile requires login. Import an authorised disclosure; a missing public hit does not mean the company is unregistered."))
            .put("coverage","Counts describe retrieved unique hits and profile candidates. Index coverage is incomplete. Account ownership needs your review.");
        if(!fresh)prefs.edit().putString(cacheKey,result.toString()).putLong(cacheKey+"-time",System.currentTimeMillis()).apply();return result;
    }
    public JSONObject tenders(String query,String status,int start) throws Exception {return tenders(query,status,start,"keyword");}
    public JSONObject tenders(String query,String status,int start,String searchBy) throws Exception {
        int number=status.equals("open")?1:status.equals("awarded")?2:status.equals("closed")?3:status.equals("cancelled")?4:0;if(number==0)throw new IOException("Unknown tender status");
        String url="https://www.etenders.gov.za/Home/PaginatedTenderOpportunities?status="+number+"&draw=1&start="+Math.max(0,start)+"&length=30&search%5Bvalue%5D="+enc(query)+"&order%5B0%5D%5Bcolumn%5D=2&order%5B0%5D%5Bdir%5D=desc";
        if(!query.isEmpty()&&!searchBy.equals("keyword")){String parameter=searchBy.equals("company")?"company":searchBy.equals("supplier")?"supplierNumber":searchBy.equals("number")?"tenderNumber":"";if(parameter.isEmpty())throw new IOException("Unknown tender search field");url=url.replace("PaginatedTenderOpportunities","TenderFilter/").replace("search%5Bvalue%5D="+enc(query),"search%5Bvalue%5D=")+"&"+parameter+"="+enc(query);}
        JSONObject raw=new JSONObject(read(url));JSONArray rows=raw.optJSONArray("data");if(rows==null)rows=new JSONArray();
        return new JSONObject().put("query",query).put("status",status).put("results",rows).put("total",raw.optInt("recordsFiltered",rows.length())).put("offset",start).put("retrieved_at",stamp()).put("source_url",PORTAL).put("coverage","Check amendments, requirements and submission method in each original notice.");
    }
    public synchronized JSONArray rules() throws Exception { return new JSONArray(prefs.getString("monitors","[]")); }
    public synchronized JSONArray alerts() throws Exception { return new JSONArray(prefs.getString("alerts","[]")); }
    public synchronized JSONObject saveRule(JSONObject data) throws Exception {
        JSONArray rules=rules();JSONObject old=null;int found=-1;
        for(int i=0;i<rules.length();i++)if(rules.getJSONObject(i).getString("id").equals(data.optString("id"))){old=rules.getJSONObject(i);found=i;break;}
        String q=data.optString("query").trim();JSONArray selected=data.optJSONArray("services");String condition=data.optString("condition","new_hit");
        if(q.length()<2||q.length()>160||selected==null||selected.length()==0||!Arrays.asList("new_hit","changed_hit").contains(condition))throw new IOException("Add a query, service and supported condition");
        for(int i=0;i<selected.length();i++)if(!Arrays.asList("web","social","government","cipc","tenders").contains(selected.getString(i)))throw new IOException("Unknown service");
        JSONObject rule=new JSONObject(data.toString()).put("id",old==null?hash(q+System.nanoTime()).substring(0,20):old.getString("id")).put("interval_minutes",Math.max(15,data.optInt("interval_minutes",120))).put("enabled",data.optBoolean("enabled",true)).put("updated_at",stamp());
        boolean reset=old==null||!old.optString("query").equals(q)||!old.optString("condition").equals(condition)||!old.optString("required_text").equals(data.optString("required_text"))||!old.optJSONArray("services").toString().equals(selected.toString());
        if(reset)rule.put("seen",new JSONObject()).put("baselines",new JSONArray()).put("status","pending").remove("last_checked");
        else {rule.put("seen",old.optJSONObject("seen")).put("baselines",old.optJSONArray("baselines"));}
        rule.put("query",q).put("created_at",old==null?stamp():old.optString("created_at"));if(found>=0)rules.put(found,rule);else rules.put(rule);
        prefs.edit().putString("monitors",rules.toString()).apply();return rule;
    }
    public synchronized JSONObject check(String id) throws Exception {
        JSONArray rules=rules(),inbox=alerts();JSONObject rule=null;int index=-1;for(int i=0;i<rules.length();i++)if(rules.getJSONObject(i).optString("id").equals(id)){rule=rules.getJSONObject(i);index=i;break;}if(rule==null)throw new IOException("Monitor not found");
        JSONObject seen=rule.optJSONObject("seen");if(seen==null)seen=new JSONObject();JSONArray baselines=rule.optJSONArray("baselines");if(baselines==null)baselines=new JSONArray();Set<String> baseline=new HashSet<>();for(int i=0;i<baselines.length();i++)baseline.add(baselines.getString(i));JSONArray statuses=new JSONArray(),newAlerts=new JSONArray(),services=rule.getJSONArray("services");
        for(int n=0;n<services.length();n++) {
            String service=services.getString(n);try {
                if(service.equals("cipc"))throw new IOException("Engine required to monitor imported CIPC disclosures. Live registry access is not connected.");
                JSONArray rows;
                if(service.equals("tenders")) {JSONArray raw=tenders(rule.getString("query"),"open",0).getJSONArray("results");rows=new JSONArray();for(int i=0;i<raw.length();i++){JSONObject t=raw.getJSONObject(i);rows.put(new JSONObject().put("id",String.valueOf(t.optInt("id"))).put("url",PORTAL).put("title",t.optString("description")).put("content_hash",hash(t.toString())));} }
                else {JSONObject d=discover(rule.getString("query"),service.equals("web")?"all":service,true);boolean success=false;JSONArray ss=d.getJSONArray("statuses");for(int i=0;i<ss.length();i++)if(ss.getJSONObject(i).optString("status").equals("completed"))success=true;if(!success)throw new IOException("Provider unavailable; baseline preserved");rows=d.getJSONArray("results");}
                for(int i=0;i<rows.length();i++){JSONObject h=rows.getJSONObject(i);String required=rule.optString("required_text");if(!required.isEmpty()&&!h.toString().toLowerCase(Locale.US).contains(required.toLowerCase(Locale.US)))continue;String key=service+":"+h.getString("id"),signature=h.optString("content_hash",hash(h.toString())),previous=seen.optString(key,"");boolean changed=rule.optString("condition").equals("new_hit")?previous.isEmpty():!previous.isEmpty()&&!previous.equals(signature);
                    if(baseline.contains(service)&&changed){String alertId=hash(id+key+signature).substring(0,24);boolean exists=false;for(int k=0;k<inbox.length();k++)if(inbox.getJSONObject(k).optString("id").equals(alertId))exists=true;if(!exists){JSONObject a=new JSONObject().put("id",alertId).put("rule_id",id).put("query",rule.getString("query")).put("service",service).put("condition",rule.getString("condition")).put("hit",h).put("created_at",stamp()).put("read",false);inbox.put(a);newAlerts.put(a);}}
                    seen.put(key,signature);
                }
                baseline.add(service);statuses.put(new JSONObject().put("service",service).put("status","completed"));
            }catch(Exception e){statuses.put(new JSONObject().put("service",service).put("status","unavailable").put("detail",e.getMessage()));}
        }
        rule.put("seen",seen).put("baselines",new JSONArray(baseline)).put("statuses",statuses).put("last_checked",stamp()).put("last_checked_ms",System.currentTimeMillis()).put("status","checked");rules.put(index,rule);
        prefs.edit().putString("monitors",rules.toString()).putString("alerts",inbox.toString()).apply();return new JSONObject().put("rule",rule).put("new_alerts",newAlerts);
    }
    public JSONObject archive(String url) throws Exception {
        byte[] raw=fetch(url,16*1024*1024,true,null);String sha=hash(raw);File dir=new File(context.getFilesDir(),"evidence");dir.mkdirs();try(FileOutputStream out=new FileOutputStream(new File(dir,sha))){out.write(raw);}
        String prefix=new String(raw,0,Math.min(raw.length,256),StandardCharsets.UTF_8).trim().toLowerCase(Locale.US);String mime=prefix.startsWith("%pdf")?"application/pdf":prefix.startsWith("<!doctype html")||prefix.startsWith("<html")?"text/html":"application/octet-stream";
        JSONObject item=new JSONObject().put("mime",mime).put("url",url).put("sha256",sha).put("bytes",raw.length).put("retrieved_at",stamp()).put("location","device_archive");
        synchronized(PublicServices.class){JSONArray records=new JSONArray(prefs.getString("evidence","[]"));boolean exists=false;for(int i=0;i<records.length();i++)if(records.getJSONObject(i).optString("sha256").equals(sha))exists=true;if(!exists)records.put(item);prefs.edit().putString("evidence",records.toString()).apply();}return item;
    }
    public String execute(String route,String method,String body) throws Exception {
        JSONObject data=new JSONObject(body);
        if(route.startsWith("/api/daily/"))return new DailyServices(context).execute(route,data);
        if(route.equals("/api/province/news")&&method.equals("POST"))return new ProvinceServices(context).news(data.optString("province"),data.optInt("days",30),data.optBoolean("refresh",false),this).toString();
        if(route.equals("/api/publication")&&method.equals("POST"))return PublicationServices.publication(data.optString("url")).toString();
        if(route.equals("/api/parties")&&method.equals("GET"))return new PartyServices(context).catalog().toString();
        if(route.equals("/api/party")&&method.equals("POST"))return new PartyServices(context).party(data.optString("code"),data.optBoolean("refresh",false)).toString();
        if(route.equals("/api/member")&&method.equals("POST"))return new PartyServices(context).member(data.optString("id"),data.optBoolean("refresh",false)).toString();
        if(route.equals("/api/discover")&&method.equals("POST"))return discover(data.optString("query"),data.optString("scope","all"),false,data.optString("topic","")).toString();
        if(route.equals("/api/tenders")&&method.equals("POST"))return tenders(data.optString("query"),data.optString("status","open"),data.optInt("start",0),data.optString("search_by","keyword")).toString();
        if(route.equals("/api/monitors"))return method.equals("GET")?rules().toString():saveRule(data).toString();
        if(route.equals("/api/monitors/check")&&method.equals("POST"))return check(data.optString("id")).toString();
        if(route.equals("/api/alerts")){JSONArray a=alerts();if(method.equals("POST")){for(int i=0;i<a.length();i++)a.getJSONObject(i).put("read",true);prefs.edit().putString("alerts",a.toString()).apply();}return a.toString();}
        if(route.equals("/api/evidence")&&method.equals("POST"))return archive(data.optString("url")).toString();
        if(route.equals("/api/evidence")&&method.equals("GET"))return prefs.getString("evidence","[]");
        throw new IOException("Connect your engine in Settings to use this collection tool.");
    }
}
