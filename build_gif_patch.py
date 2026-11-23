from hashlib import sha256
from pathlib import Path
import struct
import re
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
STOCK = ROOT / "stock-Carnival-TKL-v5.uf2"
CANDIDATE = ROOT / "Carnival-TKL-v5-Next-GIF-experimental.uf2"

BASE = 0x08020000
STOCK_SHA256 = "73418e9ffb78f243892fcf7db735f7f76a000c0b2b311409b2c22d45afcd2a05"
KEY_HOOK = 0x08022C32
DISPLAY_HOOK = 0x08022670
KEY_CODE = 0x0803E000
DISPLAY_CODE = 0x0803E080

def wide_branch(address, target, link=False):
    offset = target - (address + 4)
    assert offset % 2 == 0 and -(1 << 24) <= offset < (1 << 24)
    sign = (offset >> 24) & 1
    j1 = 1 ^ sign ^ ((offset >> 23) & 1)
    j2 = 1 ^ sign ^ ((offset >> 22) & 1)
    first = 0xF000 | (sign << 10) | ((offset >> 12) & 0x3FF)
    second = (0xD000 if link else 0x9000) | (j1 << 13) | (j2 << 11) | ((offset >> 1) & 0x7FF)
    return struct.pack("<HH", first, second)

def assemble(text, address):
    # The assembler resolves local labels. Absolute calls are filled in after
    # the ELF gives us their exact locations in .text.
    pending = []
    def placeholder(match):
        pending.append((int(match.group(2), 16), match.group(1) == "bl"))
        return f".inst.w 0xf7f0a{len(pending):03x}"
    text = re.sub(r"(b\.w|bl) #0x([0-9a-f]+)", placeholder, text)
    with TemporaryDirectory() as directory:
        source = Path(directory, "stub.s")
        obj = Path(directory, "stub.o")
        source.write_text(".syntax unified\n.thumb\n.text\n" + text + "\n")
        subprocess.run(["clang", "-target", "arm-none-eabi", "-mcpu=cortex-m4",
                        "-mthumb", "-c", str(source), "-o", str(obj)], check=True)
        elf = obj.read_bytes()
    assert elf[:6] == b"\x7fELF\x01\x01"
    section_offset = struct.unpack_from("<I", elf, 32)[0]
    section_size, section_count, names_index = struct.unpack_from("<3H", elf, 46)
    sections = [struct.unpack_from("<10I", elf, section_offset+i*section_size)
                for i in range(section_count)]
    names = sections[names_index]
    table = elf[names[4]:names[4]+names[5]]
    entry, = [section for section in sections
              if table[section[0]:].split(b"\0", 1)[0] == b".text"]
    program = bytearray(elf[entry[4]:entry[4]+entry[5]])
    for i, (target, link) in enumerate(pending, 1):
        marker = struct.pack("<HH", 0xF7F0, 0xA000 | i)
        assert program.count(marker) == 1
        location = program.index(marker)
        program[location:location+4] = wide_branch(address + location, target, link)
    return bytes(program)

def flash_offset(address):
    return address - BASE

def apply_patch(image):
    patched = bytearray(image)

    def replace(address, old, new):
        start = flash_offset(address)
        assert len(old) == len(new)
        assert patched[start:start + len(old)] == old
        patched[start:start + len(new)] = new

    # Reuse the existing USER04 assignment. The stock dispatch reaches this
    # site only on key-down. No filesystem calls run inside key processing.
    key_code = assemble("""
        movw r3, #0x7e04
        cmp r4, r3
        bne other_key
        movw r1, #0x0240
        movt r1, #0x2000
        ldrb r2, [r1]
        cbz r2, consume
        movw r1, #0xcb60
        movt r1, #0x2000
        ldr r2, [r1]
        tst r2, #2
        bne consume
        movw r1, #0x0210
        movt r1, #0x2000
        ldr r2, [r1, #0x1c]
        cbz r2, consume
        add.w r2, r2, #0x1000
        ldrh.w r2, [r2, #0x446]
        cmp r2, #2
        blo consume
        movs r2, #2
        str r2, [r1, #0x18]
    consume:
        b.w #0x08022c4c
    other_key:
        b.w #0x08022cbc
    """, KEY_CODE)

    # The mode field is a 32-bit word with stock values 0 (single) and
    # 1 (automatic). Value 2 queues a skip and selects single-clip looping.
    # This hook is on the stock display task's frame-fetch path. Its caller
    # already excludes storage mode and this path has no queued LCD frame.
    display_code = assemble("""
        ldr r1, [r4, #0x18]
        cmp r1, #2
        bne stock_frame
        movs r1, #0
        str r1, [r4, #0x18]
        bl #0x080272a4
        ldr r0, [r4, #0x1c]
    stock_frame:
        add.w r5, r4, #0x14
        b.w #0x08022674
    """, DISPLAY_CODE)

    # Startup's initialized-data image ends at 0x0803d6e4. Both stubs sit
    # inside checked zero padding within the existing stock UF2 blocks.
    assert len(key_code) < DISPLAY_CODE - KEY_CODE
    for address, code in [(KEY_CODE, key_code), (DISPLAY_CODE, display_code)]:
        assert address >= 0x0803d6e4
        assert flash_offset(address) + len(code) <= len(image)
        replace(address, bytes(len(code)), code)

    replace(KEY_HOOK, bytes.fromhex("47f60463"), assemble("b.w #0x0803e000", KEY_HOOK))
    replace(DISPLAY_HOOK, bytes.fromhex("04f11405"), assemble("b.w #0x0803e080", DISPLAY_HOOK))
    return bytes(patched)

def stock_image():
    stock = STOCK.read_bytes()
    assert sha256(stock).hexdigest() == STOCK_SHA256
    assert len(stock) % 512 == 0
    count = len(stock) // 512
    payload = bytearray()
    for i in range(count):
        block = stock[i * 512:(i + 1) * 512]
        assert struct.unpack_from("<8I", block) == (
            0x0a324655, 0x9e5d5157, 0x2000, BASE + 256*i,
            256, i, count, 0x57755a57,
        )
        assert struct.unpack_from("<I", block, 508)[0] == 0x0ab16f30
        payload.extend(block[32:288])
    return stock, bytes(payload)

def build():
    stock, payload = stock_image()
    result = bytearray(stock)
    image = apply_patch(payload)
    count = len(stock) // 512
    for i in range(count):
        result[i*512+32:i*512+288] = image[i*256:(i+1)*256]
    for i in range(count):
        lo, hi = i*512, (i+1)*512
        assert result[lo:lo+32] == stock[lo:lo+32]
        assert result[lo+288:hi] == stock[lo+288:hi]
    return bytes(result), image

if __name__ == "__main__":
    uf2, image = build()
    CANDIDATE.write_bytes(uf2)
    print(f"Candidate SHA-256 {sha256(uf2).hexdigest()}")
