"""Verify the expanded UF2 and emulate the changed control paths."""
from hashlib import sha256
from struct import pack, unpack_from

from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4,
    UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_LR, UC_ARM_REG_PC,
)

from build_display_controls import BINDINGS, CANDIDATE, STATE, build
from build_gif_patch import BASE, CANDIDATE as OLD_CANDIDATE
from verify_gif_patch import Harness, OBJ, MODE, ENABLE, FRAME_READY, LCD_BUSY, STORAGE

uf2, image = build()
assert CANDIDATE.read_bytes() == uf2
assert len(uf2) == len(OLD_CANDIDATE.read_bytes())
old = OLD_CANDIDATE.read_bytes()
for i in range(0, len(uf2), 512):
    assert uf2[i:i+32] == old[i:i+32]
    assert uf2[i+288:i+512] == old[i+288:i+512]
assert unpack_from("<I", image, 0x22E8)[0] == STATE
assert sha256(uf2).digest() != sha256(old).digest()
assert len({r[2] for r in BINDINGS.values()}) == 5

SUSPENDED = 0x2000CB54
GRID = 0x20008998
GRID_RENDER_CONFIG = 0x200090BC
RGB_PAUSE = 0x200090B8
TYPE_STATUS = 0x20012000

class Controls(Harness):
    def __init__(self, **kwargs):
        self.stop_at = set()
        self.destination = None
        self.lcd_ready = True
        super().__init__(**kwargs)
        self.cpu.mem_write(BASE, image)
        self.w(GRID+4,TYPE_STATUS)
        self.w(TYPE_STATUS+3,0,1)
        self.w(GRID+0x1c,1,1)
        self.w(GRID+0x1d,2,1)
        self.w(GRID+0x1e,3,1)
        self.cpu.mem_write(GRID+0x1f,b"test\0"+bytes(6))

    def dispatch(self,cpu,addr,size,data):
        if addr in self.stop_at:
            self.destination=addr
            self.end=True
            cpu.emu_stop()
            return
        if addr == 0x08020D40:
            dst=cpu.reg_read(UC_ARM_REG_R0)
            src=cpu.reg_read(UC_ARM_REG_R1)
            count=cpu.reg_read(UC_ARM_REG_R2)
            cpu.mem_write(dst,bytes(cpu.mem_read(src,count)))
        elif addr == 0x08022ECC:
            self.calls.append(("save_typing",self.r(cpu.reg_read(UC_ARM_REG_R1),1)))
        elif addr == 0x080249B6:
            self.calls.append(("reset_grid_text",0))
        elif addr == 0x080225E4:
            self.calls.append(("lcd_power",cpu.reg_read(UC_ARM_REG_R0)))
        elif addr == 0x0802290E:
            cpu.reg_write(UC_ARM_REG_R0,int(self.lcd_ready))
            self.calls.append(("lcd_ready",int(self.lcd_ready)))
        else:
            return super().dispatch(cpu,addr,size,data)
        cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))

    def checkpoint(self,entry,reg_values,*destinations):
        self.stop_at=set(destinations)
        self.destination=None
        for reg,value in reg_values.items():
            self.cpu.reg_write(reg,value)
        try:
            self.run(entry,0)
            return self.destination
        finally:
            self.stop_at.clear()

# Real firmware get/set for typing, with EEPROM and text redraw mocked.
h=Controls()
assert h.press(0x7e09,False)==1 and h.r(TYPE_STATUS+3,1)==0
assert h.press(0x7e09)==0 and h.r(TYPE_STATUS+3,1)==1
assert h.calls==[("save_typing",0x9d),("reset_grid_text",0)]
assert h.press(0x7e09)==0 and h.r(TYPE_STATUS+3,1)==0
assert h.calls[-2:]==[("save_typing",0x1d),("reset_grid_text",0)]
assert bytes(h.cpu.mem_read(GRID+0x1f,5))==b"test\0"

# Force automatic playback, preserve the prior Next GIF behavior, and
# verify that other control presses do not select a different mode.
h=Controls()
assert h.press(0x7e0a)==0 and h.r(MODE)==1
assert h.press(0x7e0a)==0 and h.r(MODE)==1
assert h.press(0x7e04)==0 and h.r(MODE)==2
h.draw()
assert h.r(MODE)==0 and ("open",1) in h.calls

# Grid blackout is a rendering override and leaves the live mode intact.
h=Controls()
h.w(GRID_RENDER_CONFIG,1,1)
registers={UC_ARM_REG_R2:GRID_RENDER_CONFIG}
path=(0x08025674,0x0802544A)
assert h.checkpoint(0x08025442,registers,*path)==0x0802544A
assert h.press(0x7e0b)==0 and h.r(STATE)==2
assert h.checkpoint(0x08025442,registers,*path)==0x08025674
assert h.cpu.reg_read(UC_ARM_REG_R5)==0 and h.r(GRID_RENDER_CONFIG,1)==1
assert h.press(0x7e0b)==0 and h.r(STATE)==0
assert h.checkpoint(0x08025442,registers,*path)==0x0802544A
h.w(GRID_RENDER_CONFIG,0,1)
assert h.checkpoint(0x08025442,registers,*path)==0x08025674

# LCD changes are deferred during USB suspend/storage and an active transfer.
h=Controls()
assert h.press(0x7e0c)==0 and h.r(STATE)==9 and h.r(ENABLE,1)==1
h.w(STORAGE,2)
h.draw()
assert h.r(STATE)==9 and h.calls==[]
h.w(STORAGE,0)
h.w(SUSPENDED,1,1)
h.w(ENABLE,0,1)
h.draw()
assert h.r(STATE)==9 and h.calls==[]
h.w(SUSPENDED,0,1)
h.w(ENABLE,1,1)
h.w(LCD_BUSY,1,1)
h.w(FRAME_READY,1,1)
h.lcd_ready=False
h.draw()
assert h.r(STATE)==9 and h.calls==[("lcd_ready",0)]
h.lcd_ready=True
h.draw()
assert h.r(STATE)==1 and h.r(ENABLE,1)==0 and h.calls[-1]==("lcd_power",0)
h.run(0x080227F4,1)
assert h.r(ENABLE,1)==0, "stock resume must honor manual LCD off"
assert h.press(0x7e0c)==0
h.draw()
assert h.r(ENABLE,1)==1 and ("lcd_power",1) in h.calls and h.r(STATE)==0

# All-off overlaps LCD-only and grid-only and restores each independently.
h=Controls()
h.press(0x7e0b)
h.press(0x7e0c)
h.press(0x7e0d)
h.draw()
assert h.r(STATE)==7 and h.r(ENABLE,1)==0
h.press(0x7e0d)
h.draw()
assert h.r(STATE)==3 and h.r(ENABLE,1)==0
regs={UC_ARM_REG_R4:0x200090B4,UC_ARM_REG_R6:RGB_PAUSE}
before=(0x0802656A,0x08026576)
after=(0x08026594,0x0802658A)
assert h.checkpoint(0x08026564,regs,*before)==0x0802656A
assert h.checkpoint(0x08026586,regs,*after)==0x08026594
h.press(0x7e0d)
assert h.checkpoint(0x08026564,regs,*before)==0x08026576
assert h.checkpoint(0x08026586,regs,*after)==0x0802658A
assert h.r(RGB_PAUSE,1)==0
h.press(0x7e0d)
h.w(RGB_PAUSE,1,1)
assert h.checkpoint(0x08026564,regs,*before)==0x08026576
assert h.checkpoint(0x08026586,regs,*after)==0x0802658A

# Standard RGB increment/decrement must still reach the original dispatch.
h=Controls()
h.stop_at={0x080266D0,0x08026700}
assert h.press(0x7821)==1 and h.destination==0x080266D0
assert h.press(0x7822)==1 and h.destination==0x08026700

print("Passed emulation of typing, auto rotation, all blackout paths, Next GIF, and RGB Mode +/− dispatch.")
