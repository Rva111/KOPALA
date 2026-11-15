"""Refresh known public PSI CSVs. Never downloads videos or changes field mappings."""
from datetime import datetime, timezone
import csv, hashlib, io, json, tempfile
from pathlib import Path
from urllib.parse import urlparse
import httpx
from datasets import DATA

ORIGIN='https://psi.nasa.gov'

def main():
    inventory=json.loads((DATA/'inventory.json').read_text(encoding='utf-8-sig'))
    staged=[]
    with httpx.Client(timeout=45,follow_redirects=False) as client, tempfile.TemporaryDirectory() as temporary:
        for investigation in inventory:
            accession=investigation['id']
            res=client.get(f'{ORIGIN}/geode-py/ws/repo/investigations/{accession}')
            res.raise_for_status();meta=res.json()
            available=[f for name in ('experimentalTable','modelingTable','added') for f in (meta.get(name) or []) if isinstance(f,dict) and not f.get('restricted') and f.get('visible',True)]
            for file in investigation['files']:
                match=next((f for f in available if f.get('file_name')==file['filename']),None)
                if match is None:raise RuntimeError(f'Known public table no longer available: {file["filename"]}; existing cache is unchanged.')
                version=match.get('version',file['version'])
                resolver=client.get(f'{ORIGIN}/geode-py/ws/studies/{accession}/download',params={'file':file['filename'],'version':version,'redirect':'false'})
                resolver.raise_for_status();url=resolver.text.strip().strip('"')
                parsed=urlparse(url)
                # Only follow the NASA API's public S3 download, never dataset-provided URLs.
                if parsed.scheme!='https' or not parsed.hostname or not (parsed.hostname.endswith('.amazonaws.com') or parsed.hostname.endswith('.nasa.gov')):
                    raise RuntimeError('NASA returned an unexpected download host; existing cache is unchanged.')
                parts=[];size=0
                with client.stream('GET',url) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>5_000_000:raise RuntimeError('CSV exceeds the small-table download limit.')
                        parts.append(chunk)
                raw=b''.join(parts)
                try:text=raw.decode('utf-8-sig')
                except UnicodeDecodeError:text=raw.decode('cp1252')
                headers=next(csv.reader(io.StringIO(text)),None)
                if headers!=file.get('expected_headers'):
                    raise RuntimeError(f'Headers changed in {file["filename"]}; review the mapping first. Existing cache is unchanged.')
                path=Path(temporary)/file['filename'];path.write_bytes(raw);staged.append((path,DATA/'originals'/file['filename']))
                file.update(version=version,size=size,sha256=hashlib.sha256(raw).hexdigest(),downloaded_utc=datetime.now(timezone.utc).date().isoformat())
                print('Checked',file['filename'])
        for source,target in staged:target.write_bytes(source.read_bytes())
        (DATA/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    print(f'Updated {len(staged)} small CSV files. Restart the app; changed files automatically invalidate answer caches.')

if __name__=='__main__':
    try:main()
    except (httpx.HTTPError,ValueError,RuntimeError) as error:
        # httpx exceptions can include temporary signed URLs: print only their class.
        if isinstance(error,httpx.HTTPError):print('NASA refresh failed:',type(error).__name__,'. Existing files were retained.')
        else:print(str(error))
        raise SystemExit(1)
