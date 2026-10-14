"""Read-only DN client resource collector. Writes a diagnostics ZIP, without editing PAKs."""
import argparse,hashlib,json,struct,zlib,zipfile
from pathlib import Path
TARGETS={'itemcompoundgrouptable.dnt','itemcompoundgrouptable_custom.dnt','itemcompoundtable_custom.dnt','itemcompoundtable_glyph.dnt','itemcompoundtable_jewel.dnt','itemcompoundtable_renewal.dnt','itemcompoundtable_set.dnt','npctable.dnt','jobtable.dnt','itemtable_equipment.dnt','weapontable_equipment.dnt','partstable_equipment.dnt','setitemtable.dnt'}
p=argparse.ArgumentParser();p.add_argument('--client-root',default=r'D:\Games\DN\Client-DN556-CN-LouLx');p.add_argument('--output',default='DN556_CLIENT_CRAFT_DIAGNOSTICS.zip');a=p.parse_args();root=Path(a.client_root)
if not root.is_dir():p.error('Client folder does not exist: '+str(root))
report={'client_folder_name':root.name,'note':'Alphabetical listing is not proof of runtime PAK priority. Only matched DNT/UI resources are exported.','packages':[],'entries':[],'errors':[]};budget=0
with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for pi,pak in enumerate(sorted(root.glob('*.pak'),key=lambda x:x.name.lower())):
  size=pak.stat().st_size;info={'name':pak.name,'bytes':size};report['packages'].append(info);print('Reading',pak.name,flush=True)
  try:
   with pak.open('rb') as f:
    header=f.read(1024)
    if len(header)!=1024 or header[:32]!=b'EyedentityGames Packing File 0.1':raise ValueError('Unsupported PAK header')
    version,count,table=struct.unpack_from('<III',header,256);info.update(version=version,file_count=count)
    if count>1000000 or table<1024 or table+count*316>size:raise ValueError('Invalid index bounds')
    f.seek(table);index=f.read(count*316)
    for i in range(count):
     o=i*316;aliases=[x.decode('ascii','replace') for x in index[o:o+256].split(b'\0') if x]
     match=next((n for n in aliases if (n.replace('\\','/').rsplit('/',1)[-1].lower() in TARGETS or (n.replace('\\','/').rsplit('/',1)[-1].lower().startswith('itemcompound') and n.lower().endswith('.dnt'))) or (n.lower().endswith(('.xml','.lua','.gml','.txt')) and any(t in n.lower() for t in ['compound','craft','makeitem','blacksmith']))),None)
     if not match:continue
     stored,original,total,offset,flags=struct.unpack_from('<5I',index,o+256)
     entry={'pak':pak.name,'paths':aliases,'selected_path':match,'stored_bytes':stored,'original_bytes':original,'flags':flags};report['entries'].append(entry)
     try:
      if original>32*1024*1024 or stored>16*1024*1024 or stored<=0 or offset<1024 or offset+stored>table:raise ValueError('Entry bounds/size limit')
      f.seek(offset);block=f.read(stored);d=zlib.decompressobj();raw=d.decompress(block,original+1)
      if not d.eof or d.unconsumed_tail or len(raw)!=original:raise ValueError('Invalid zlib stream or length')
      if budget+len(raw)>28*1024*1024:raise ValueError('Export limit reached; request a narrower export')
      budget+=len(raw);base=match.replace('\\','/').rsplit('/',1)[-1];safe=''.join(c for c in base if c.isalnum() or c in '._-');name=f'resources/pak_{pi:03d}_entry_{i:06d}_{safe}'
      entry.update(exported_file=name,sha256=hashlib.sha256(raw).hexdigest());z.writestr(name,raw)
     except Exception as ex:entry['error']=str(ex)
  except Exception as ex:info['error']=str(ex);report['errors'].append({'pak':pak.name,'error':str(ex)})
 report['all_packages_read']=not report['errors'];report['all_matching_entries_extracted']=all('exported_file' in e for e in report['entries']);report['exported_original_bytes']=budget
 z.writestr('client_resource_manifest.json',json.dumps(report,ensure_ascii=False,indent=2))
print('Created:',str(Path(a.output).resolve()));print('Matched entries:',len(report['entries']),'errors:',len(report['errors'])+sum('error' in e for e in report['entries']))
