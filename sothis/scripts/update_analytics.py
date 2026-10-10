#!/usr/bin/env python3
"""Capture official seat/results sources, or install a reviewed newer manifest.

--reviewed-json replaces the dated results and optional national polls atomically.
The UI selects the newest election and retires polls for the previous cycle.
Use --sources-dir for an already downloaded set of the official source files.
"""
import argparse
import hashlib
import json
import math
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.analytics import DATA, validate
from engine.core import now

SEATS = 'https://www.parliament.gov.za/national-assembly'
PREVIOUS = 'https://www.parliament.gov.za/press-releases/current-composition-newly-sworn-6th-parliament'
PROVINCIAL = 'https://results.elections.org.za/home/NPEPublicReports/1335/Results%20Report/National.pdf'
BOUNDARIES = 'https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/9469f09/releaseData/gbOpen/ZAF/ADM1/geoBoundaries-ZAF-ADM1_simplified.geojson'
NAMES = ['Eastern Cape','Free State','Gauteng','KwaZulu-Natal','Limpopo','Mpumalanga','North West','Northern Cape','Western Cape']
ALIASES = {'ALJAMA':"ALJAMA'AH", 'ACTIONSA':'ActionSA', 'VFPLUS':'FF PLUS', 'FFPLUS':'FF PLUS', 'M.K.':'MK', 'CCC':'NCC', 'RISE':'RISE MZANSI'}
COLORS = {'ANC':'#e6bd45','DA':'#4388ff','MK':'#61ac77','EFF':'#ee6567','IFP':'#cc8e59','PA':'#8fc39d','FF PLUS':'#ff975f','ActionSA':'#74b679','ACDP':'#a693ed','UDM':'#66bbb4','RISE MZANSI':'#bda587','BOSA':'#b9c0cc','ATM':'#a3c2cf',"ALJAMA'AH":'#71acac','NCC':'#d3a2b5','PAC':'#8dac63','UAT':'#b9ad8e','GOOD':'#daaa7e'}


def plain(raw):
    return re.sub(r'\s+', ' ', unescape(re.sub('<[^>]+>', ' ', raw))).strip()


def provincial_rows(extracted, codes):
    # Every IEC row has nine province pairs plus the total pair; the source
    # extraction can wrap both the party name and abbreviation over lines.
    rows = {}
    pair = r'([\d,]+)\s+([\d.]+)\s*%'
    for code in codes:
        abbr = {"ALJAMA'AH":'ALJAMA', 'ActionSA':r'ACTION\s*SA', 'FF PLUS':r'VF\s*PLUS', 'MK':r'M\.K\.', 'NCC':'CCC', 'RISE MZANSI':r'RISE'}.get(code, re.escape(code))
        match = re.search(r'(?m)^'+abbr+r'\s*\n(?=\d)', extracted)
        if not match:
            raise ValueError('IEC abbreviation not found: '+code)
        pairs = re.findall(pair, extracted[match.end():])[:10]
        if len(pairs) != 10:
            raise ValueError('Incomplete IEC row: '+code)
        rows[code] = [{'votes':int(v.replace(',','')), 'share':float(s)} for v,s in pairs]
    return rows


def simplify(points, tolerance=.025):
    if len(points) < 3:
        return points
    a,b = points[0],points[-1]
    dx,dy = b[0]-a[0],b[1]-a[1]
    def distance(p):
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
        return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    i=max(range(1,len(points)-1),key=lambda i:distance(points[i]))
    if distance(points[i]) > tolerance:
        return simplify(points[:i+1],tolerance)[:-1]+simplify(points[i:],tolerance)
    return [a,b]


def map_paths(geo):
    result={}
    def xy(p):return ((p[0]-16.2)*math.cos(math.radians(30))*31,(-p[1]-21.7)*31)
    for f in geo['features']:
        name=f['properties']['shapeName'].replace('Nothern','Northern').replace('KwaZulu Natal','KwaZulu-Natal')
        polygons=f['geometry']['coordinates'] if f['geometry']['type']=='MultiPolygon' else [f['geometry']['coordinates']]
        parts=[]
        for polygon in polygons:
            for ring in polygon:
                reduced=simplify(ring)
                if len(reduced)<4:continue
                pts=[xy(p) for p in reduced]
                parts.append('M'+'L'.join(f'{x:.1f},{y:.1f}' for x,y in pts)+'Z')
        result[name]=''.join(parts)
    if set(result)!=set(NAMES):raise ValueError('Unexpected boundary names')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-dir',type=Path)
    parser.add_argument('--reviewed-json',type=Path)
    args=parser.parse_args()
    if args.reviewed_json:
        data=validate(json.loads(args.reviewed_json.read_text()))
    else:
        def get(name,url):
            if args.sources_dir:return (args.sources_dir/name).read_bytes()
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Sothis/0.5 evidence capture'}),timeout=30) as r:
                return r.read(20*1024*1024)
        raw=get('national-analytics.html',SEATS);old=get('national-2019',PREVIOUS)
        seat_text=plain(raw.decode()); old_text=plain(old.decode())
        parties=json.loads((DATA.parent/'party-data.json').read_text())['parties']
        codes=[p['code'] for p in parties]
        current={}
        for p in parties:
            label={'MK':'Umkhonto we Sizwe','RISE MZANSI':'RISE Mzansi','UAT':'United Africans Transformation'}.get(p['code'],p['name'])
            # Use the row's Number of Seats, never its separate percentage column.
            code=p['code']
            for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',raw.decode(),re.S|re.I):
                cells=[plain(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',row,re.S|re.I)]
                if len(cells)==4 and (party_name_key(cells[1].split('(')[0])==party_name_key(label) or re.search(r'\('+re.escape(code)+r'\)',cells[1],re.I)):
                    if cells[3].isdigit():current[code]=int(cells[3]);break
            if code not in current:raise ValueError('Seat row not found: '+code)
        # Source names use different party typography. Parse all historic rows.
        historic={}
        names={'FF PLUS':'Freedom Front Plus',"ALJAMA'AH":'Al Jama’ah','GOOD':'Good','PAC':'Pan Africanist Congress of Azania'}
        for p in parties:
            match=re.search(re.escape(names.get(p['code'],p['name']))+r'\s*(?:\([^)]*\))?\s*[–-]\s*[\d.]+%,\s*(\d+) seats?',old_text,re.I)
            historic[p['code']]=int(match[1]) if match else 0
        for code,name in [('NFP','National Freedom Party'),('AIC','African Independent Congress'),('COPE','Congress of the People')]:
            match=re.search(re.escape(name)+r'\s*\([^)]*\)\s*[–-]\s*[\d.]+%,\s*(\d+) seats?',old_text,re.I)
            if not match:raise ValueError('Historic party missing: '+code)
            historic[code]=int(match[1])
        pdf=get('provincial-2024',PROVINCIAL)
        from pypdf import PdfReader
        import io
        extracted='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(pdf)).pages)
        rows=provincial_rows(extracted,codes)
        paths=map_paths(json.loads(get('geo-simple-real.json',BOUNDARIES)))
        provinces=[]
        for i,name in enumerate(NAMES):
            results=sorted([dict(code=c,**rows[c][i]) for c in codes],key=lambda r:-r['votes'])
            provinces.append(dict(name=name,path=paths[name],leader=results[0]['code'],results=results))
        captured=now()
        data=dict(schema_version=1,captured_at=captured,colors=COLORS,
            national_elections=[dict(date='2019-05-08',total_seats=400,seats=historic,source_url=PREVIOUS,source_hash=hashlib.sha256(old).hexdigest()),dict(date='2024-05-29',total_seats=400,seats=current,source_url=SEATS,source_hash=hashlib.sha256(raw).hexdigest())],
            provincial_election=dict(date='2024-05-29',ballot='Provincial Ballot',reported_at='2024-06-21T13:51:28+02:00',source_url=PROVINCIAL,source_hash=hashlib.sha256(pdf).hexdigest(),coverage='Provincial-ballot plurality, not coalition control. Charts cover the 18 parties in the current Parliament directory; other parties and independents also contested.'),
            provinces=provinces,map_credit=dict(source='geoBoundaries / OCHA ROSEA / South African Municipal Demarcation Board',url='https://www.geoboundaries.org/api/current/gbOpen/ZAF/ADM1/',license='CC BY 3.0 IGO',license_url='https://creativecommons.org/licenses/by/3.0/igo/',boundary_year=2020),polls=[])
        validate(data)
    temporary=DATA.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temporary.replace(DATA)
    print('Saved',DATA,'· latest election',max(e['date'] for e in data['national_elections']))


def party_name_key(s):return re.sub(r'[^a-z]','',s.casefold())
if __name__=='__main__':main()
