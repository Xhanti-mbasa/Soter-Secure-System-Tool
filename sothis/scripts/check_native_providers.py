#!/usr/bin/env python3
"""Run the native parser/filter methods on a JVM, using supplied JSON-java.

Production method bodies are extracted directly; the Android Html conversion is
represented by a narrow text double. No requests or Android hardware are used.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
JAVA = ROOT / 'android/app/src/main/java/za/co/zalens'


def segment(source, start, stop):
    return source[source.index(start):source.index(stop, source.index(start))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-jar', required=True, type=Path)
    args = parser.parse_args()
    public = (JAVA / 'PublicServices.java').read_text()
    daily = (JAVA / 'DailyServices.java').read_text()
    search = segment(public, '    static JSONArray searchRows(', '    private void cacheDiscovery(')
    filters = segment(public, '    static String tenderValues(', '    public JSONObject tenders(String query,String status,int start,String searchBy)')
    jobs = segment(daily, '    JSONArray jobs(', '    JSONArray feed(')
    dates = segment(daily, '    private static String localDate(', '    JSONArray jobs(')
    source = r'''package za.co.zalens;
import org.json.*;import java.util.*;import java.util.regex.*;import java.net.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.time.*;import java.security.*;
class PublicServices {
 static String clean(String value){return value.replaceAll("<[^>]+>"," ").replace("&amp;","&").replaceAll("\\s+"," ").trim();}
 static String hash(String value)throws Exception{StringBuilder s=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)))s.append(String.format("%02x",b&255));return s.toString();}
 static String stamp(){return Instant.now().toString();}
''' + search + filters + r'''}
class DailyServices {
 static final String EC="https://erecruitment.ecotp.gov.za/Process/JobTitle.aspx";
''' + dates + jobs + r'''}
public final class NativeProvidersTest {
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 public static void main(String[] args)throws Exception {
  String html="<table><tr><td><span id='gvAllJobs_ctl02_lblJobTitle'>Library <span>Assistant</span></span><b>Salary label must not enter title</b><span id=\"gvAllJobs_ctl02_lblDescription\">Grade 12<br/>Library skills</span><b>Posted on:</b><span id='gvAllJobs_ctl02_lblPostDate'>01/01/2020</span><b>Closing on:</b><span id='gvAllJobs_ctl02_lblClosingDate'>23/10/2099</span><b>Apply</b></td></tr></table>";
  JSONArray jobs=new DailyServices().jobs(html);check(jobs.length()==1,"Readable nested vacancy");JSONObject job=jobs.getJSONObject(0);
  check(job.getString("title").equals("Library Assistant"),"Title must stop at its matching span");check(job.getString("description").equals("Grade 12 Library skills"),"Description excludes sibling labels");check(job.getString("closing_at").equals("2099-10-23"),"Closing date excludes adjacent text");
  check(new DailyServices().jobs(html.replace("23/10/2099","01/01/2020")).length()==0,"All readable expired vacancies are a real empty result");
  JSONArray search=PublicServices.searchRows("<a class='result-link' href='//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Falex&amp;rut=a'>Alex Example</a>");check(search.length()==1,"Single-quoted public result");check(search.getJSONObject(0).getString("url").equals("https://example.org/alex"),"Decode ordinary public redirect");
  check(PublicServices.searchRows("<p>No results found</p>").length()==0,"Explicit empty search");for(String invalid:Arrays.asList("<p>CAPTCHA</p>","<form id='challenge-form'>Continue</form>","<html>Changed layout</html>")){boolean rejected=false;try{PublicServices.searchRows(invalid);}catch(IOException expected){rejected=true;}check(rejected,"Unknown/challenged search pages cannot be completed zero");}
  JSONObject tender=new JSONObject("{\"id\":1,\"description\":\"Construction of a library\",\"tender_No\":\"QA-123/26\",\"awards\":[{\"company\":\"Library Construction\",\"supplierNumber\":\"MAAA12345\"}]}");
  check(PublicServices.tenderMatches(tender,"construction library","keyword"),"Every keyword appears");check(!PublicServices.tenderMatches(tender,"ZZZNOMATCH","keyword"),"Ignored upstream query cannot invent a match");check(PublicServices.tenderMatches(tender,"QA123","number"),"Compact tender number");check(!PublicServices.tenderMatches(tender,"---","number"),"No empty-normalized number match");check(PublicServices.tenderMatches(tender,"Library Construction","company"),"Company award values");check(!PublicServices.tenderMatches(new JSONObject("{\"awards\":null}"),"company","company"),"JSON property names are not supplier evidence");check(PublicServices.tenderMatches(tender,"MAAA12345","supplier"),"Supplier award values");
  System.out.println("Native provider parsing passed: nested span boundaries, dates, expiry, public search markup/challenges and verified tender/award matching.");
 }
}
'''
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        file = root / 'NativeProvidersTest.java'
        file.write_text(source)
        classes = root / 'classes'
        classes.mkdir()
        subprocess.run(['javac', '-source', '8', '-target', '8', '-cp', str(args.json_jar), '-d', str(classes), str(file)], check=True)
        subprocess.run(['java', '-cp', str(classes) + ':' + str(args.json_jar), 'za.co.zalens.NativeProvidersTest'], check=True)


if __name__ == '__main__':
    main()
