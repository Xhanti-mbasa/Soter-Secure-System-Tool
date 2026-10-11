#!/usr/bin/env python3
"""Compare isolated provider scheduling against the retained feature release.

Uses controlled 40 ms readers and two distinct cold-cache providers. It measures
service overhead/concurrency, not internet response times or physical devices.
"""
import importlib.util,json,statistics,subprocess,sys,time,types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from engine.daily import DailyService
from test_daily import RSS,JOB

def measure(Service):
 samples=[]
 for _ in range(10):
  def reader(url):time.sleep(.04);return JOB if 'erecruitment' in url else RSS
  svc=Service(reader);start=time.perf_counter()
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(svc.collect,'news',{});b=pool.submit(svc.collect,'opportunities',{})
   assert len(a.result()['results'])==1 and len(b.result()['results'])==1
  samples.append((time.perf_counter()-start)*1000)
 return round(statistics.median(samples),2)

if __name__=='__main__':
 baseline=subprocess.check_output(['git','log','-1','--format=%H','--grep=^sothis: release 0.7.0'],cwd=ROOT).decode().strip()
 if not baseline:raise SystemExit('Fetch the retained 0.7.0 feature commit before benchmarking')
 source=subprocess.check_output(['git','show',baseline+':sothis/engine/daily.py'],cwd=ROOT).decode()
 module=types.ModuleType('engine.daily_baseline');module.__package__='engine';exec(source,module.__dict__)
 result={'controlled_parallel_provider_ms_feature':measure(module.DailyService),'controlled_parallel_provider_ms_optimized':measure(DailyService),'reader_delay_ms':40,'pairs_per_version':10}
 print(json.dumps(result,indent=2))
