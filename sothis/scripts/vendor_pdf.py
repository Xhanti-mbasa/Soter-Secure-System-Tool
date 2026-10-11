#!/usr/bin/env python3
"""Rebuild pinned, local classic-script PDF.js assets with Terser 5.44.0.

Supply the upstream 5.4.296 pdf.mjs/pdf.worker.mjs files and the installed
Terser binary. Source hashes are verified before transformation.
"""
import argparse,hashlib,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SOURCES={'pdf.mjs': '5d408104b55dfa88bd542df8520798dd449504157933efeb638c30664902419d', 'pdf.worker.mjs': '044d2faff688e8502bdfa8e91222dc2420443f9a35f5d9a8ed06d9de6c39bb28'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--terser',type=Path,required=True);args=p.parse_args()
 for filename,expected in SOURCES.items():
  path=args.source_dir/filename;raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Unexpected upstream source: '+filename)
  source=raw.decode();match=re.search(r'export\s*\{([^}]+)\};?',source)
  if not match:raise ValueError('Expected final ESM export block')
  aliases=[]
  for item in match.group(1).split(','):
   names=item.strip().split(' as ');aliases.append(names[-1]+':'+names[0])
  name='pdfjsLib' if filename=='pdf.mjs' else 'pdfjsWorker'
  adapted='(function(){\n'+source[:match.start()].replace('import.meta.url','"file:///sothis-pdf-local.js"')+'\nglobalThis.'+name+'={'+','.join(aliases)+'};\n})();\n'
  with tempfile.TemporaryDirectory() as temporary:
   input=Path(temporary)/'input.js';input.write_text(adapted)
   output=ROOT/'android/app/src/main/assets/vendor'/filename.replace('.mjs','.js')
   subprocess.run(['node',str(args.terser),str(input),'--compress','passes=1','--mangle','--keep-classnames','--format','comments=/@license|Copyright/','--output',str(output)],check=True)
   subprocess.run(['node','--check',str(output)],check=True)
   print(output.name,len(raw),'->',output.stat().st_size,'bytes')
if __name__=='__main__':main()
