package za.co.zalens;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.*;
import org.xmlpull.v1.*;
import java.io.StringReader;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.*;
import java.util.regex.*;

/** Everyday provider boundary. Profiles/CVs stay local; no automatic submissions. */
public final class DailyServices {
    static final String EC="https://erecruitment.ecotp.gov.za/Process/JobTitle.aspx";
    private final Context context;
    interface DailyProvider {JSONArray load(String url)throws Exception;}
    private final Map<String,DailyProvider> providers=new HashMap<>();
    private final Object[] cacheStripes=new Object[32];
    private final Object cacheWrite=new Object();
    DailyServices(Context context){this.context=context;for(int i=0;i<cacheStripes.length;i++)cacheStripes[i]=new Object();providers.put("/api/daily/news",new FeedProvider());providers.put("/api/daily/opportunities",new VacancyProvider());}
    private final class FeedProvider implements DailyProvider {public JSONArray load(String url)throws Exception{return feed(url);}}
    private final class VacancyProvider implements DailyProvider {public JSONArray load(String url)throws Exception{if(!EC.equals(url))throw new Exception("Unknown vacancy provider");return jobs(read(url));}}
    private String read(String url)throws Exception{return new String(PublicServices.fetch(url,2*1024*1024,true,null),StandardCharsets.UTF_8);}
    private static String localDate(String s){try{String[] p=s.trim().split("/");return LocalDate.of(Integer.parseInt(p[2]),Integer.parseInt(p[1]),Integer.parseInt(p[0])).toString();}catch(Exception e){return "";}}
    JSONArray jobs(String html)throws Exception{
        JSONArray out=new JSONArray();boolean readable=false;
        Pattern ids=Pattern.compile("<span\\b[^>]*\\bid\\s*=\\s*([\"'])(gvAllJobs_ctl[0-9]+)_(lbl[A-Za-z]+)\\1[^>]*>",Pattern.CASE_INSENSITIVE);
        Matcher m=ids.matcher(html);Map<String,Map<String,String>> rows=new LinkedHashMap<>();
        while(m.find()){
            Matcher spans=Pattern.compile("<(\\/?)span\\b[^>]*>",Pattern.CASE_INSENSITIVE).matcher(html);spans.region(m.end(),html.length());int depth=1,end=-1;
            while(spans.find()){depth+=spans.group(1).isEmpty()?1:-1;if(depth==0){end=spans.start();break;}}
            if(end<0)continue;Map<String,String> row=rows.get(m.group(2));if(row==null){row=new HashMap<>();rows.put(m.group(2),row);}row.put(m.group(3),PublicServices.clean(html.substring(m.end(),end)));
        }
        for(Map<String,String> f:rows.values()){String title=f.get("lblJobTitle");if(title==null||title.isEmpty())continue;readable=true;String close=localDate(f.containsKey("lblClosingDate")?f.get("lblClosingDate"):"");if(!close.isEmpty()&&close.compareTo(LocalDate.now(ZoneOffset.UTC).toString())<0)continue;
            String location=f.containsKey("lblCity")?f.get("lblCity"):"",description=f.containsKey("lblDescription")?f.get("lblDescription"):"";
            out.put(new JSONObject().put("id",PublicServices.hash(title+"|"+location+"|"+close).substring(0,24)).put("title",title.substring(0,Math.min(500,title.length()))).put("description",description.substring(0,Math.min(8000,description.length()))).put("salary",f.containsKey("lblPackage")?f.get("lblPackage"):"").put("employer",f.containsKey("lblDepartment")?f.get("lblDepartment"):"").put("location",location).put("province","Eastern Cape").put("url",EC).put("published_at",localDate(f.containsKey("lblPostDate")?f.get("lblPostDate"):"")).put("closing_at",close).put("retrieved_at",PublicServices.stamp()).put("publisher","Eastern Cape Provincial eRecruitment").put("application_method","official_portal_handoff").put("verified_listing",true));if(out.length()>=100)break;
        }
        if(out.length()==0&&!readable)throw new Exception("No readable current vacancies; use the official portal");return out;
    }
    JSONArray feed(String url)throws Exception{
        URI u=new URI(url);if(!"https".equals(u.getScheme())||u.getUserInfo()!=null)throw new Exception("Feeds require HTTPS");String raw=read(url);
        if(url.equals(ProvinceServices.FEED)){JSONArray a=ProvinceServices.parse(raw);for(int i=0;i<a.length();i++)a.getJSONObject(i).put("reader_allowed",true).put("credit","SAnews.gov.za");return a;}
        if(raw.toUpperCase(Locale.US).contains("<!DOCTYPE")||raw.toUpperCase(Locale.US).contains("<!ENTITY"))throw new Exception("Unsupported XML");
        XmlPullParserFactory factory=XmlPullParserFactory.newInstance();factory.setNamespaceAware(true);XmlPullParser p=factory.newPullParser();p.setInput(new StringReader(raw));Map<String,String> f=null;JSONArray a=new JSONArray();Set<String> seen=new HashSet<>();boolean valid=false;
        for(int event=p.getEventType();event!=XmlPullParser.END_DOCUMENT;event=p.next()){
            if(event==XmlPullParser.START_TAG){String tag=p.getName();if(Arrays.asList("rss","feed","RDF").contains(tag))valid=true;if(tag.equals("item")||tag.equals("entry"))f=new HashMap<>();else if(f!=null&&Arrays.asList("title","link","pubDate","published").contains(tag)){String href=p.getAttributeValue(null,"href");f.put(tag,href!=null?href:p.nextText());}}
            else if(event==XmlPullParser.END_TAG&&f!=null&&(p.getName().equals("item")||p.getName().equals("entry"))){try{String link=f.get("link"),title=PublicServices.clean(f.get("title"));URI target=new URI(link);if(!"https".equals(target.getScheme())||target.getUserInfo()!=null||seen.contains(link))throw new Exception();a.put(new JSONObject().put("id",PublicServices.hash(link).substring(0,24)).put("url",link).put("title",title).put("description","").put("publisher",u.getHost()).put("published_at",ProvinceServices.date(f.containsKey("pubDate")?f.get("pubDate"):f.get("published"))).put("reader_allowed",false).put("retrieved_at",PublicServices.stamp()));seen.add(link);}catch(Exception ignored){}f=null;if(a.length()>=100)break;}
        }
        if(!valid)throw new Exception("Not an RSS/Atom feed");return a;
    }
    String execute(String route,JSONObject data)throws Exception{
        if(route.equals("/api/daily/article")){String url=data.getString("url");URI u=new URI(url);if(!"https".equals(u.getScheme())||!Arrays.asList("www.sanews.gov.za","sanews.gov.za").contains(u.getHost())||u.getUserInfo()!=null)throw new Exception("Open this publisher directly");String html=read(url).replaceAll("(?is)<(script|style|nav|header|footer)[^>]*>.*?</\\1>","");String text=PublicServices.clean(html);return new JSONObject().put("url",url).put("text",text.substring(0,Math.min(40000,text.length()))).put("publisher","SAnews.gov.za").put("reader_allowed",true).toString();}
        DailyProvider provider=providers.get(route);if(provider==null)throw new Exception("Unknown daily service");
        boolean news=route.equals("/api/daily/news");String name=data.optString("province"),query=data.optString("query").toLowerCase(Locale.US).trim();JSONArray definitions=new JSONObject(ProvinceServices.asset(context,"province-data.json")).getJSONArray("provinces"),keywords=new JSONArray();boolean known=name.isEmpty();for(int i=0;i<definitions.length();i++){JSONObject d=definitions.getJSONObject(i);if(d.getString("name").equals(name)){keywords=d.getJSONArray("keywords");known=true;}}if(!known)throw new Exception("Unknown province");
        List<String> urls=new ArrayList<>();urls.add(news?ProvinceServices.FEED:EC);JSONArray custom=data.optJSONArray("feeds");if(custom!=null&&custom.length()>3)throw new Exception("Choose up to three custom feeds");if(news&&custom!=null)for(int i=0;i<custom.length();i++)urls.add(custom.getString(i));JSONArray rows=new JSONArray(),statuses=new JSONArray();Set<String> seen=new HashSet<>();SharedPreferences prefs=context.getSharedPreferences("daily",Context.MODE_PRIVATE);
        for(String url:urls){try{String key=PublicServices.hash(url);JSONArray items;synchronized(cacheStripes[Math.floorMod(key.hashCode(),cacheStripes.length)]){String prior=prefs.getString(key,"");if(!data.optBoolean("refresh")&&!prior.isEmpty()&&System.currentTimeMillis()-prefs.getLong(key+"-time",0)<300000)items=new JSONArray(prior);else{items=provider.load(url);synchronized(cacheWrite){SharedPreferences.Editor edit=prefs.edit();if(!prefs.contains(key)&&prefs.getAll().size()>=64){String oldest="";long stamp=Long.MAX_VALUE;for(String k:prefs.getAll().keySet())if(k.endsWith("-time")&&prefs.getLong(k,0)<stamp){oldest=k;stamp=prefs.getLong(k,0);}if(!oldest.isEmpty()){edit.remove(oldest);edit.remove(oldest.substring(0,oldest.length()-5));}}edit.putString(key,items.toString()).putLong(key+"-time",System.currentTimeMillis()).apply();}}}
            for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);String hay=(item.optString("title")+" "+item.optString("description")+" "+item.optString("location")).toLowerCase(Locale.US);boolean relevant=name.isEmpty()||name.equals(item.optString("province"));for(int j=0;j<keywords.length();j++)if(hay.contains(keywords.getString(j).toLowerCase(Locale.US)))relevant=true;boolean match=true;for(String token:query.split("\\s+"))if(!hay.contains(token))match=false;String id=item.getString("id"),date=item.optString("published_at"),close=item.optString("closing_at");if(!close.isEmpty()&&close.compareTo(LocalDate.now(ZoneOffset.UTC).toString())<0)match=false;if(date.length()>=10&&date.substring(0,10).compareTo(LocalDate.now(ZoneOffset.UTC).toString())>0)match=false;if(relevant&&match&&!seen.contains(id)){rows.put(item);seen.add(id);}}
            statuses.put(new JSONObject().put("provider",url).put("status","completed").put("count",items.length()));
        }catch(Exception e){statuses.put(new JSONObject().put("provider",url).put("status","unavailable").put("detail",String.valueOf(e.getMessage())));}}
        return new JSONObject().put("results",rows).put("statuses",statuses).put("retrieved_at",PublicServices.stamp()).put("coverage","Publisher feed items and supported public vacancies. Other official providers open in your browser.").toString();
    }
}
