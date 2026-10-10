package za.co.zalens;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;
import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserFactory;
import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.*;
import java.util.regex.Pattern;

/** Public publisher feed; geography and publication windows match the hosted engine. */
public final class ProvinceServices {
    static final String FEED="https://www.sanews.gov.za/south-africa-news-stories.xml";
    private final Context context;
    ProvinceServices(Context context){this.context=context;}
    public static String asset(Context context,String name) throws Exception {
        try(InputStream in=context.getAssets().open(name)){
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[8192];int n;
            while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>3*1024*1024)throw new IOException("Asset size limit");}
            return new String(out.toByteArray(),StandardCharsets.UTF_8);
        }
    }
    static String date(String value){
        if(value==null||value.isEmpty())return "";
        try{return Instant.parse(value).toString();}catch(Exception ignored){}
        try{SimpleDateFormat format=new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss Z",Locale.US);format.setLenient(false);Date d=format.parse(value);return d.toInstant().toString();}catch(Exception ignored){return "";}
    }
    static JSONArray parse(String xml) throws Exception {
        if(xml.length()>2*1024*1024||xml.toUpperCase(Locale.US).contains("<!DOCTYPE")||xml.toUpperCase(Locale.US).contains("<!ENTITY"))throw new IOException("Unsupported news feed");
        XmlPullParserFactory factory=XmlPullParserFactory.newInstance();factory.setNamespaceAware(true);XmlPullParser parser=factory.newPullParser();parser.setInput(new StringReader(xml));
        List<JSONObject> items=new ArrayList<>();Set<String> seen=new HashSet<>();Map<String,String> fields=null;boolean valid=false;int event=parser.getEventType();
        while(event!=XmlPullParser.END_DOCUMENT){
            if(event==XmlPullParser.START_TAG){String tag=parser.getName();
                if(tag.equals("rss")||tag.equals("feed")||tag.equals("RDF"))valid=true;
                if(tag.equals("item")||tag.equals("entry"))fields=new HashMap<>();
                else if(fields!=null&&Arrays.asList("title","link","description","summary","pubDate","published","date").contains(tag)){
                    String href=tag.equals("link")?parser.getAttributeValue(null,"href"):null;
                    fields.put(tag,href!=null?href:parser.nextText());
                }
            }else if(event==XmlPullParser.END_TAG&&fields!=null&&(parser.getName().equals("item")||parser.getName().equals("entry"))){
                String url=fields.containsKey("link")?fields.get("link").trim():"";String title=PublicServices.clean(fields.containsKey("title")?fields.get("title"):"");
                try{URI u=new URI(url);if(!u.getScheme().equals("https")||u.getUserInfo()!=null||!Arrays.asList("www.sanews.gov.za","sanews.gov.za").contains(u.getHost()))throw new IOException();url=new URI(u.getScheme(),u.getAuthority(),u.getPath(),u.getQuery(),null).toString();if(title.isEmpty()||seen.contains(url))throw new IOException();
                    String description=PublicServices.clean(fields.containsKey("description")?fields.get("description"):fields.containsKey("summary")?fields.get("summary"):"");title=title.substring(0,Math.min(500,title.length()));description=description.substring(0,Math.min(1200,description.length()));String published=date(fields.containsKey("pubDate")?fields.get("pubDate"):fields.containsKey("published")?fields.get("published"):fields.get("date"));
                    items.add(new JSONObject().put("id",PublicServices.hash(url).substring(0,24)).put("url",url).put("title",title).put("description",description).put("publisher","SAnews / GCIS").put("category","government").put("published_at",published.isEmpty()?JSONObject.NULL:published).put("publication_date_source",published.isEmpty()?JSONObject.NULL:"Publisher RSS publication field").put("retrieved_at",PublicServices.stamp()).put("content_hash",PublicServices.hash(title+"\n"+description)).put("acquisition","publisher_feed"));seen.add(url);
                }catch(Exception ignored){}
                fields=null;if(items.size()>=100)break;
            }
            event=parser.next();
        }
        if(!valid)throw new IOException("Publisher returned an unsupported feed");
        JSONArray output=new JSONArray();for(JSONObject item:items)output.put(item);return output;
    }
    public JSONObject news(String name,int days,boolean refresh,PublicServices services) throws Exception {
        JSONObject p=null;JSONArray provinces=new JSONObject(asset(context,"province-data.json")).getJSONArray("provinces");
        for(int i=0;i<provinces.length();i++)if(provinces.getJSONObject(i).getString("name").equals(name))p=provinces.getJSONObject(i);
        if(p==null||!(days==7||days==30||days==90||days==0))throw new IOException("Select a province and a supported news window");
        JSONArray keywords=p.getJSONArray("keywords"),statuses=new JSONArray(),undated=new JSONArray(),candidates=new JSONArray();List<JSONObject> matches=new ArrayList<>();boolean cached=false;
        try{
            JSONArray items;
            synchronized(ProvinceServices.class){SharedPreferences prefs=context.getSharedPreferences("services",Context.MODE_PRIVATE);String prior=prefs.getString("province-news-feed","");cached=!refresh&&!prior.isEmpty()&&System.currentTimeMillis()-prefs.getLong("province-news-time",0)<300000;
                if(cached)items=new JSONArray(prior);else{items=parse(new String(PublicServices.fetch(FEED,2*1024*1024,true,null),StandardCharsets.UTF_8));prefs.edit().putString("province-news-feed",items.toString()).putLong("province-news-time",System.currentTimeMillis()).apply();}
            }
            LocalDate today=LocalDate.now(ZoneOffset.UTC),start=today.minusDays(days);
            for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);String hay=item.getString("title")+" "+item.optString("description");boolean relevant=false;
                for(int j=0;j<keywords.length();j++)if(Pattern.compile("(?<![\\p{L}\\p{N}_])"+Pattern.quote(keywords.getString(j))+"(?![\\p{L}\\p{N}_])",Pattern.CASE_INSENSITIVE|Pattern.UNICODE_CASE).matcher(hay).find())relevant=true;
                if(!relevant)continue;String pub=item.optString("published_at","");if(pub.isEmpty()||pub.equals("null")){if(undated.length()<20)undated.put(item);continue;}
                LocalDate d=Instant.parse(pub).atOffset(ZoneOffset.UTC).toLocalDate();if(d.isAfter(today)||days>0&&d.isBefore(start))continue;matches.add(item);
            }
            statuses.put(new JSONObject().put("service","SAnews publisher feed").put("status","completed").put("retrieved",items.length()).put("matched",matches.size()));
        }catch(Exception e){statuses.put(new JSONObject().put("service","SAnews publisher feed").put("status","unavailable").put("detail",e.getMessage()==null?"Feed unavailable":e.getMessage()));}
        Collections.sort(matches,new Comparator<JSONObject>(){public int compare(JSONObject a,JSONObject b){return b.optString("published_at").compareTo(a.optString("published_at"));}});
        if(matches.isEmpty()){JSONObject discovery=services.discover(name,"all",refresh,"news");candidates=discovery.getJSONArray("results");JSONArray more=discovery.getJSONArray("statuses");for(int i=0;i<more.length();i++)statuses.put(more.getJSONObject(i));}
        JSONArray results=new JSONArray();for(int i=0;i<Math.min(40,matches.size());i++)results.put(matches.get(i));
        return new JSONObject().put("province",name).put("days",days).put("results",results).put("undated",undated).put("candidates",candidates).put("statuses",statuses).put("retrieved_at",PublicServices.stamp()).put("cached",cached).put("source_url",FEED).put("coverage","Dated articles mention this province or a listed locality. The feed contains a limited set of recent publisher items. Public-index candidates need an original publication-date check before they can be treated as current news.");
    }
}
