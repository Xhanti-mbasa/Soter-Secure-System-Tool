package za.co.zalens;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Official public representatives, separate from unverified web mentions. */
public final class PartyServices {
    private static final String PARLIAMENT="https://www.parliament.gov.za";
    private final JSONObject snapshot;
    private final SharedPreferences prefs;

    public PartyServices(Context context) throws Exception {
        prefs=context.getSharedPreferences("parties",Context.MODE_PRIVATE);
        snapshot=new JSONObject(snapshot(context));
    }

    public static String snapshot(Context context) throws Exception {
        try(InputStream in=context.getAssets().open("party-data.json");ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);
            return new String(out.toByteArray(),StandardCharsets.UTF_8);
        }
    }

    static String group(String expression,String body) throws IOException {
        Matcher m=Pattern.compile(expression,Pattern.DOTALL|Pattern.CASE_INSENSITIVE).matcher(body);
        if(!m.find())throw new IOException("Parliament page format changed; saved evidence retained");
        return m.group(1);
    }

    private JSONObject savedParty(String code) throws Exception {
        JSONArray parties=snapshot.getJSONArray("parties");
        for(int i=0;i<parties.length();i++){
            JSONObject p=parties.getJSONObject(i);
            if(p.getString("code").equalsIgnoreCase(code)){
                return new JSONObject(prefs.getString("party-"+p.getString("code"),p.toString()));
            }
        }
        throw new IOException("Choose a party from the public Parliament directory");
    }

    public JSONObject catalog() throws Exception {
        JSONArray result=new JSONArray(),parties=snapshot.getJSONArray("parties");
        for(int i=0;i<parties.length();i++){JSONObject p=savedParty(parties.getJSONObject(i).getString("code"));p.remove("members");result.put(p);}
        return new JSONObject().put("parties",result).put("captured_at",snapshot.getString("captured_at")).put("coverage",snapshot.getString("coverage"));
    }

    public JSONObject party(String code,boolean refresh) throws Exception {
        JSONObject p=savedParty(code);p.put("status","saved_roster");
        if(refresh)try {
            String url=PARLIAMENT+"/members-of-parliament",raw=PublicServices.read(url);
            String component=group("<group-details\\b([^>]+)>",raw);
            JSONObject groups=new JSONObject(PublicServices.clean(group("members='([^']*)'",component)));
            int expected=Integer.parseInt(group("member-count='(\\d+)'",component)),total=0;
            JSONArray members=new JSONArray();java.util.HashSet<String> ids=new java.util.HashSet<>(),codes=new java.util.HashSet<>();
            JSONArray known=snapshot.getJSONArray("parties");for(int i=0;i<known.length();i++)codes.add(known.getJSONObject(i).getString("code"));
            java.util.Iterator<String> keys=groups.keys();
            while(keys.hasNext()){
                JSONArray rows=groups.getJSONArray(keys.next());
                for(int i=0;i<rows.length();i++){
                    JSONObject row=rows.getJSONObject(i);String id=row.getString("id"),party=row.getString("party");
                    if(!id.matches("\\d{1,10}")||!ids.add(id)||!codes.contains(party))throw new IOException("Invalid, duplicated or unknown-party directory entry");total++;
                    if(party.equals(p.getString("code")))members.put(new JSONObject().put("id",id).put("name",row.getString("full_name")).put("party_code",party).put("source_url",PARLIAMENT+"/person-details/"+id));
                }
            }
            if(total!=expected||total==0)throw new IOException("Incomplete Parliament directory");
            java.util.ArrayList<JSONObject> sorted=new java.util.ArrayList<>();for(int i=0;i<members.length();i++)sorted.add(members.getJSONObject(i));java.util.Collections.sort(sorted,new java.util.Comparator<JSONObject>(){public int compare(JSONObject a,JSONObject b){return a.optString("name").compareToIgnoreCase(b.optString("name"));}});members=new JSONArray();for(JSONObject row:sorted)members.put(row);
            p.put("source_url",url);
            p.put("members",members).put("member_count",members.length()).put("captured_at",PublicServices.stamp()).put("content_hash",PublicServices.hash(raw)).put("status","refreshed");
            prefs.edit().putString("party-"+p.getString("code"),p.toString()).apply();
        }catch(Exception e){p.put("status","refresh_unavailable").put("detail",e.getMessage());}
        return p.put("coverage",snapshot.getString("coverage"));
    }

    public JSONObject member(String id,boolean refresh) throws Exception {
        if(!id.matches("\\d{1,10}"))throw new IOException("Invalid Parliament member ID");
        JSONObject p=null,m=null;JSONArray parties=snapshot.getJSONArray("parties");
        for(int i=0;i<parties.length()&&m==null;i++){
            JSONObject candidate=savedParty(parties.getJSONObject(i).getString("code"));JSONArray members=candidate.getJSONArray("members");
            for(int j=0;j<members.length();j++)if(members.getJSONObject(j).getString("id").equals(id)){p=candidate;m=new JSONObject(members.getJSONObject(j).toString());break;}
        }
        if(m==null)throw new IOException("Member is not in the captured public roster");
        m.put("party_name",p.getString("name")).put("roster_url",p.getString("source_url")).put("captured_at",p.opt("captured_at"));
        JSONObject seed=snapshot.getJSONObject("profiles").optJSONObject(id);
        if(seed!=null){java.util.Iterator<String> keys=seed.keys();while(keys.hasNext()){String k=keys.next();m.put(k,seed.get(k));}}
        JSONObject cached=new JSONObject(prefs.getString("member-"+id,"{}"));java.util.Iterator<String> keys=cached.keys();while(keys.hasNext()){String k=keys.next();m.put(k,cached.get(k));}
        m.put("status",m.has("profile_captured_at")?"saved_profile":"roster_only");
        if(refresh)try {
            String raw=PublicServices.read(PARLIAMENT+"/person-details/"+id);
            String body=group("<div[^>]*class=[\"'][^\"']*\\bmember-info\\b[^\"']*[\"'][^>]*>(.*?)<div\\s+id=[\"']contact-details",raw);
            String name=PublicServices.clean(group("<h2[^>]*>(.*?)</h2>",body));
            Matcher greens=Pattern.compile("<span[^>]*class=[\"']green[\"'][^>]*>(.*?)</span>",Pattern.DOTALL|Pattern.CASE_INSENSITIVE).matcher(body);java.util.ArrayList<String> values=new java.util.ArrayList<>();while(greens.find())values.add(PublicServices.clean(greens.group(1)));
            if(values.isEmpty())throw new IOException("Incomplete member summary");
            String partyName=values.get(values.size()-1),role=values.size()>1?values.get(values.size()-2):"",chamber="";
            Matcher c=Pattern.compile("<span[^>]*class=[\"']label[^\"']*[\"'][^>]*>(.*?)</span>",Pattern.DOTALL|Pattern.CASE_INSENSITIVE).matcher(body);if(c.find())chamber=PublicServices.clean(c.group(1));
            m.put("name",name).put("party_name",partyName).put("role",role).put("chamber",chamber).put("profile_captured_at",PublicServices.stamp()).put("profile_content_hash",PublicServices.hash(raw)).put("status","refreshed");
            if(!partyName.equalsIgnoreCase(p.getString("name")))m.put("party_code",JSONObject.NULL).put("membership_note","Member page differs from saved party roster. Refresh the roster and review both sources.");
            else {m.put("party_code",p.getString("code"));m.remove("membership_note");}
            prefs.edit().putString("member-"+id,m.toString()).apply();
        }catch(Exception e){m.put("status","refresh_unavailable").put("detail",e.getMessage());}
        String role=m.optString("role").toLowerCase(java.util.Locale.US);
        String payRole=role.startsWith("deputy minister")?"Deputy Minister":role.startsWith("minister")?"Minister":role.equals("deputy president")?"Deputy President":"";
        m.put("remuneration",JSONObject.NULL);JSONArray scales=snapshot.getJSONArray("remuneration_schedules");
        for(int i=0;i<scales.length();i++)if(scales.getJSONObject(i).getString("role").equals(payRole))m.put("remuneration",scales.getJSONObject(i));
        if(!m.has("search_name"))m.put("search_name",m.getString("name").replaceFirst("^(Mr|Ms|Mrs|Dr|Prof|Rev|Hon)\\.?\\s+",""));
        return m.put("interests_register",snapshot.getJSONObject("interests_register")).put("coverage","Public representative profile. Public biography and dated disclosures have their own sources; news mentions do not prove relationships.");
    }
}
