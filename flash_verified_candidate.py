import argparse
import hashlib
import os
from pathlib import Path
import plistlib
import subprocess

if not __debug__:
    raise SystemExit("Run with Python assertions enabled so the device and image are verified.")

parser = argparse.ArgumentParser(description='Flash the verified Carnival TKL Next GIF candidate from macOS.')
parser.add_argument('--location-id', required=True, type=lambda value: int(value, 0),
                    help='USB locationID recorded while the Carnival TKL was in normal keyboard mode')
args = parser.parse_args()

drive = Path('/Volumes/BOOT')
source = Path(__file__).resolve().with_name('Carnival-TKL-v5-Next-GIF-experimental.uf2')
digest = 'ae83a327c89c90e92f886a0954b49372ab0a1666593f74614316384057973bb2'
data = source.read_bytes()
assert len(data) == 257536 and hashlib.sha256(data).hexdigest() == digest

def nodes(objects):
    for obj in objects:
        yield obj
        yield from nodes(obj.get('IORegistryEntryChildren', []))

usb = plistlib.loads(subprocess.check_output(['ioreg', '-a', '-p', 'IOUSB', '-l', '-w0']))
if isinstance(usb, dict):
    usb = [usb]
boot, = [d for d in nodes(usb) if d.get('USB Product Name') == 'Boot Device']
assert boot['locationID'] == args.location_id
assert (boot['idVendor'],boot['idProduct']) == (0x4d58,0x4266)
assert not any(d.get('USB Product Name') == 'Carnival TKL' for d in nodes(usb))
assert drive.is_mount()
disk = plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(drive)]))
assert disk['MountPoint'] == str(drive) and disk['BusProtocol'] == 'USB'
assert disk['VolumeName'] == 'BOOT' and not disk['Internal']
assert 'docs.iatkb.com' in (drive/'DOCS.HTM').read_text().lower()
assert not list(drive.glob('*.UF2'))

with (drive/'NEXTGIF.UF2').open('xb') as file:
    assert file.write(data) == len(data)
    file.flush()
    os.fsync(file.fileno())
print('Wrote and synced all 257,536 firmware bytes.')
