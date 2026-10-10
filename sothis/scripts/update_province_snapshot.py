#!/usr/bin/env python3
"""Rebuild dated province evidence; optional --register-dir contains verified DHET PDFs.

Population uses the comparable Census 2022 table, not a 2026 headcount.
QLFS figures below are reviewed Q2 2026 table 2.3 values (counts in thousands).
Private register pages are search candidates, never inferred accreditation records.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'android/app/src/main/assets'
CAPTURE = '2026-10-10'
CENSUS = 'https://census.statssa.gov.za/assets/documents/2022/P03014_Census_2022_Statistical_Release.pdf'
QLFS = 'https://www.statssa.gov.za/publications/P0211/P02112ndQuarter2026.pdf'
NSC = 'https://www.education.gov.za/Portals/0/Documents/Reports/2025%20NSC%20Examination%20Report.pdf'
UNIVERSITIES = 'https://usaf.ac.za/prospective-students/'
TVET = 'https://www.careerhelp.org.za/content/education-system-south-africa/tvet-and-university'
PHEI = 'https://www.dhet.gov.za/Registers_DocLib/Register%20Phei%20%2012%20August.pdf'
PRIVATE_COLLEGES = 'https://www.dhet.gov.za/Registers_DocLib/Register%20of%20Private%20Colleges%20%2016%20September%202026.pdf'

# name, census population, absorption %, unemployment %, participation %, employed thousands,
# working age thousands, QLFS PDF page, NSC wrote, NSC achieved, NSC %, keywords for news/registers.
ROWS = [
 ('Eastern Cape',7230204,28.9,47.5,55.1,1346,4653,36,106561,89694,84.17,['Eastern Cape','Gqeberha','East London','Bhisho','Mthatha','Port Elizabeth','Alice']),
 ('Free State',2964412,39.6,37.3,63.1,769,1945,38,38205,34129,89.33,['Free State','Bloemfontein','Welkom','Mangaung']),
 ('Gauteng',15099422,43.9,34.6,67.2,5094,11595,42,140927,125513,89.06,['Gauteng','Johannesburg','Pretoria','Tshwane','Ekurhuleni','Sandton','Midrand']),
 ('KwaZulu-Natal',12423907,34.8,32.5,51.6,2725,7825,40,171368,155258,90.60,['KwaZulu-Natal','KwaZulu Natal','KZN','Durban','eThekwini','Pietermaritzburg','Richards Bay']),
 ('Limpopo',6572720,36.6,32.0,53.9,1512,4133,45,100973,86986,86.15,['Limpopo','Polokwane','Thohoyandou','Tzaneen','Mankweng']),
 ('Mpumalanga',5143324,39.1,36.6,61.7,1270,3247,44,67114,58084,86.55,['Mpumalanga','Mbombela','Nelspruit','Emalahleni','eMalahleni','Witbank']),
 ('North West',3804548,30.6,38.1,49.5,878,2868,41,40913,36205,88.49,['North West','North-West','Mahikeng','Mafikeng','Rustenburg','Potchefstroom']),
 ('Northern Cape',1355946,36.3,28.7,51.0,309,852,38,14084,12365,87.79,['Northern Cape','Kimberley','Upington','Kuruman']),
 ('Western Cape',7433019,54.6,19.5,67.8,2835,5193,34,65965,58181,88.20,['Western Cape','Cape Town','Stellenbosch','George','Bellville','Paarl']),
]
UNI = {
 'Eastern Cape':[('Nelson Mandela University','mandela.ac.za'),('Rhodes University','ru.ac.za'),('University of Fort Hare','ufh.ac.za'),('Walter Sisulu University','wsu.ac.za')],
 'Free State':[('University of the Free State','ufs.ac.za'),('Central University of Technology','cut.ac.za')],
 'Gauteng':[('University of Johannesburg','uj.ac.za'),('University of Pretoria','up.ac.za'),('University of the Witwatersrand','wits.ac.za'),('University of South Africa','unisa.ac.za'),('Tshwane University of Technology','tut.ac.za'),('Vaal University of Technology','vut.ac.za'),('Sefako Makgatho Health Sciences University','smu.ac.za')],
 'KwaZulu-Natal':[('University of KwaZulu-Natal','ukzn.ac.za'),('University of Zululand','unizulu.ac.za'),('Durban University of Technology','dut.ac.za'),('Mangosuthu University of Technology','mut.ac.za')],
 'Limpopo':[('University of Limpopo','ul.ac.za'),('University of Venda','univen.ac.za')],
 'Mpumalanga':[('University of Mpumalanga','ump.ac.za')],
 'North West':[('North-West University','nwu.ac.za')],
 'Northern Cape':[('Sol Plaatje University','spu.ac.za')],
 'Western Cape':[('University of Cape Town','uct.ac.za'),('Stellenbosch University','sun.ac.za'),('University of the Western Cape','uwc.ac.za'),('Cape Peninsula University of Technology','cput.ac.za')],
}
COLLEGES = {
 'Eastern Cape':['Buffalo City','Eastcape Midlands','Ikhala','Ingwe','King Hintsa','King Sabata Dalindyebo','Lovedale','Port Elizabeth'],
 'Free State':['Flavius Mareka','Goldfields','Maluti','Motheo'],
 'Gauteng':['Central Johannesburg','Ekurhuleni East','Ekurhuleni West','Sedibeng','South West Gauteng','Tshwane North','Tshwane South','Western'],
 'KwaZulu-Natal':['Coastal KZN','Elangeni','Esayidi','Majuba','Mnambithi','Mthashana','Thekwini','Umfolozi','Umgungundlovu'],
 'Limpopo':['Capricorn','Lephalale','Letaba','Mopani South East','Sekhukhune','Vhembe','Waterberg'],
 'Mpumalanga':['Ehlanzeni','Gert Sibande','Nkangala'],
 'North West':['Orbit','Taletso','Vuselela'],
 'Northern Cape':['Northern Cape Rural','Northern Cape Urban'],
 'Western Cape':['Boland','College of Cape Town','False Bay','Northlink','South Cape','West Coast'],
}
SECTORS = [
 ('statistics','Population, households & services','Stats SA Census and data portal','https://census.statssa.gov.za/','Public census tables: age, households, housing, water, electricity and internet. Periods vary.'),
 ('economy','Economy, industries & jobs','Stats SA ISIbalo data portal','https://isibaloweb.statssa.gov.za/pages/dataapps.php','GDP, labour, agriculture, manufacturing and trade tables. Check geography and release date for each series.'),
 ('banks','Banks & co-operative banks','SARB Prudential Authority','https://www.resbank.co.za/en/home/what-we-do/Prudentialregulation/sa-registered-banks-and-representative-offices','Official institution lists; national licences do not identify every provincial branch or customers.'),
 ('finance','Financial providers, funds & insurers','FSCA registers','https://www.fsca.co.za/FSB-Search/','Verify provider names and FSP numbers. The regulator has additional registers for funds, insurers and other entities.'),
 ('companies','Companies & co-operatives','CIPC / BizPortal','https://www.bizportal.gov.za/','Open the official portal and import an authorised disclosure. Authentication and access conditions apply; no public ownership API is assumed.'),
 ('markets','Listed companies','JSE','https://www.jse.co.za/','Issuer announcements and public company reporting. Search the issuer and verify the publication period.'),
 ('groups','Nonprofit organisations & groups','Department of Social Development','https://www.dsd.gov.za/','Use the official NPO services and register. An NPO entry is not a complete list of informal or political groups.'),
 ('budgets','Budgets & public entities','National Treasury','https://www.treasury.gov.za/','Provincial budgets, expenditure publications and PFMA entity schedules. Inspect the original report year.'),
 ('municipal','Municipal finance & performance','Municipal Money / National Treasury','https://municipalmoney.gov.za/','Municipal finances and audit context; select the municipality inside this province.'),
 ('procurement','Tenders & awarded contracts','National Treasury eTenders','https://www.etenders.gov.za/Home/opportunities','Published open and awarded tenders; the app also provides live tender lookup in Tools.'),
 ('health','Health facilities & public health','National Department of Health','https://www.health.gov.za/','Public facilities, policies and aggregate reports. Personal medical records are excluded.'),
 ('crime','Crime statistics','South African Police Service','https://www.saps.gov.za/services/crimestats.php','Published aggregates by reporting period and police station. Counts do not establish individual guilt.'),
 ('environment','Parks, conservation & activities','South African National Parks','https://www.sanparks.org/','Park information, conservation reports and visitor activities. Verify availability with the park.'),
 ('tourism','Tourism, events & things to do','South African Tourism','https://www.southafrica.net/','Explore provincial destinations, cultural activities and tourism information. Event dates must be checked with the organiser.'),
 ('education','Qualifications & provider accreditation','SAQA / QCTO','https://www.saqa.org.za/','Qualification registration; provider accreditation and DHET registration are distinct checks.'),
 ('training','Occupational training providers','Quality Council for Trades and Occupations','https://www.qcto.org.za/','Occupational provider accreditation. Some occupational providers are exempt from the DHET private-college register.'),
]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--register-dir',type=Path);args=parser.parse_args()
 result={'schema_version':1,'captured_at':CAPTURE,'coverage':'Reviewed provincial indicators and public directories. This is not every public database or a complete campus inventory.','sources':{
  'population':{'url':CENSUS,'period':'Census 2022','published_at':'2023-10-10','page':15,'definition':'Census population, table 2.1. Historic count; not a current population estimate.'},
  'labour':{'url':QLFS,'period':'Q2 2026 · April–June','published_at':'2026-08-11','definition':'QLFS, ages 15–64, table 2.3. Estimates and rounding apply. Absorption uses the working-age population; unemployment uses the labour force.'},
  'nsc':{'url':NSC,'period':'NSC class of 2025','published_at':'2026-01-12','page':6,'definition':'DBE full-time candidates who wrote and achieved the NSC. This is not a pass rate for all schools, all grades or an entire learner cohort.'},
  'latest_population':{'url':'https://www.statssa.gov.za/?PPN=P0302&page_id=1854','period':'Mid-year population estimates 2026','definition':'Newer estimates are available from Stats SA. The comparable provincial census values remain separate until the provincial estimate table is imported and reviewed.'}},
  'education_outcomes':[
   {'id':'ieb','name':'Independent schools · IEB NSC','value':98.31,'period':'2025','geography':'National IEB candidates','source_url':'https://www.ieb.co.za/post/2025-ieb-national-senior-certificate-results','published_at':'2026-01-12','definition':'National IEB NSC pass rate; no provincial breakdown is installed. IEB is not every independent school.'},
   {'id':'sacai','name':'Independent / distance schooling · SACAI','source_url':'https://www.sacai.org.za/','definition':'No reviewed provincial pass-rate series installed. Consult the assessment body’s dated results.'},
   {'id':'tvet','name':'TVET · NC(V) & Report 191','source_url':'https://www.dhet.gov.za/SitePages/Statistics-on-Post-School-Education-and-Training.aspx','definition':'Completion/certification varies by qualification, level and examination sitting. No reviewed province series installed.'},
   {'id':'cet','name':'Community & adult education','source_url':'https://www.dhet.gov.za/SitePages/Community%20Education%20and%20Training.aspx','definition':'CET/AET outcomes are separate from matric. No reviewed provincial series installed.'},
   {'id':'higher','name':'Public & private higher education','source_url':'https://www.che.ac.za/','definition':'Course success, graduation and cohort completion use different denominators. No reviewed provincial series installed.'},
   {'id':'basic','name':'Primary school & earlier grades','source_url':'https://www.education.gov.za/Resources/Reports.aspx','definition':'Learning assessments and grade progression are separate measures. No universal provincial primary-school pass-rate measure is installed.'}],
  'sectors':[dict(id=i,name=n,publisher=p,url=u,description=d,access='Public directory / original publisher',captured_at=CAPTURE) for i,n,p,u,d in SECTORS],
  'provinces':[]}
 for name,pop,absorption,unemployment,participation,employed,working,page,wrote,passed,rate,aliases in ROWS:
  result['provinces'].append({'name':name,'keywords':aliases,'population':pop,'labour':{'absorption':absorption,'unemployment':unemployment,'participation':participation,'employed_thousands':employed,'working_age_thousands':working,'page':page},'nsc':{'wrote':wrote,'achieved':passed,'pass_rate':rate},'universities':[{'name':n,'url':'https://www.'+domain+'/','source_url':UNIVERSITIES,'type':'Public university','location_basis':'Primary province; this university may have campuses or distance learners elsewhere.'} for n,domain in UNI[name]],'tvet_colleges':[{'name':n+' TVET College' if 'College' not in n else n,'source_url':TVET,'type':'Public TVET college'} for n in COLLEGES[name]]})
 (ASSETS/'province-data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 if args.register_dir:
  from pypdf import PdfReader
  registers=[]
  for ident,filename,url,date in [('private_he','phei.pdf',PHEI,'2026-08-12'),('private_college','private-colleges.pdf',PRIVATE_COLLEGES,'2026-09-16')]:
   path=args.register_dir/filename;raw=path.read_bytes()
   if not raw.startswith(b'%PDF'):raise ValueError('Expected verified PDF: '+str(path))
   reader=PdfReader(path);pages=[]
   for i,page in enumerate(reader.pages):
    original=page.extract_text() or ''
    # Display only institutional information, not personal phone/email contacts.
    cleaned='\n'.join(line for line in original.splitlines() if not re.search(r'@|\b(?:Tel|Fax|Cell|CONTACT PERSON)\b',line,re.I))
    pages.append({'page':i+1,'text':cleaned,'text_hash':hashlib.sha256(cleaned.encode()).hexdigest(),'source_text_hash':hashlib.sha256(original.encode()).hexdigest()})
   registers.append({'id':ident,'name':'DHET private higher education institutions' if ident=='private_he' else 'DHET private colleges','updated_at':date,'source_url':url,'pdf_sha256':hashlib.sha256(raw).hexdigest(),'pages':pages,'coverage':'Searchable PDF page extracts, including registration conditions, programmes and cancellation sections. Text matches and page counts are not counts of registered institutions. Read the original entry and its section before making a registration claim.'})
  (ASSETS/'education-registers.json').write_text(json.dumps({'captured_at':CAPTURE,'registers':registers},ensure_ascii=False,separators=(',',':'))+'\n')
 print('Nine provinces, 26 public universities, 50 public TVET colleges; evidence dates preserved.')

if __name__=='__main__':main()
