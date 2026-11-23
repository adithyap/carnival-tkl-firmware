from capstone import Cs, CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP
from build_gif_patch import (
    BASE, CANDIDATE, DISPLAY_CODE, DISPLAY_HOOK, KEY_CODE, KEY_HOOK, build, stock_image,
)

uf2, image = build()
assert CANDIDATE.read_bytes() == uf2
_, stock = stock_image()
diffs = [BASE+i for i,(old,new) in enumerate(zip(stock,image,strict=True)) if old != new]
assert all(any(start <= addr < end for start,end in (
    (KEY_HOOK,KEY_HOOK+4),(DISPLAY_HOOK,DISPLAY_HOOK+4),
    (KEY_CODE, KEY_CODE+128),(DISPLAY_CODE, DISPLAY_CODE+64)))
    for addr in diffs)
for start,target in [(KEY_HOOK,KEY_CODE),(DISPLAY_HOOK,DISPLAY_CODE)]:
    ins, = Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(image[start-BASE:start-BASE+4],start)
    assert ins.mnemonic == "b.w" and int(ins.op_str.removeprefix("#"),16) == target

OBJ, ANIM, EVENT = 0x20000210, 0x20009000, 0x2000e000
MODE, STORAGE, ENABLE = OBJ+0x18, 0x2000cb60, 0x20000240
TOTAL, CURRENT = ANIM+0x1446, ANIM+0x1448
FRAME_READY, LCD_BUSY = 0x20000814, 0x20000815
RETURN = 0x0803f600

class Harness:
    def __init__(self, count=2, current=0, mode=0, storage=False, enabled=True):
        self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.cpu.mem_map(BASE,0x20000)
        self.cpu.mem_write(BASE,image)
        self.cpu.mem_map(0x20000000,0x20000)
        self.w(MODE,mode)
        self.w(STORAGE,2 if storage else 0)
        self.w(ENABLE,int(enabled),1)
        self.w(OBJ+0x1c,ANIM)
        self.w(TOTAL,count,2)
        self.w(CURRENT,current,2)
        self.calls=[]
        self.end=False
        self.key=0
        self.completed_frame=False
        self.cpu.hook_add(UC_HOOK_CODE,self.dispatch)
    def w(self,addr,val,size=4):
        self.cpu.mem_write(addr,val.to_bytes(size,'little'))
    def r(self,addr,size=4):
        return int.from_bytes(self.cpu.mem_read(addr,size),'little')
    def dispatch(self,cpu,addr,size,data):
        if addr==RETURN:
            self.end=True
            cpu.emu_stop()
            return
        mocks={
            0x0802a9c4:(self.key,None),
            0x0802b434:(0,None),
            0x08026f18:(1,'open'),
            0x080271e8:(0 if self.completed_frame else 1,'frame'),
            0x08027e90:(100,'elapsed'),
            0x08022916:(0,'transfer'),
            0x08027e7e:(101,'clock'),
            0x0802290e:(0,'busy'),
            0x0802666c:(0,'other_rgb'),
        }
        if addr in mocks:
            value,name=mocks[addr]
            if name:
                self.calls.append((name,self.r(CURRENT,2)))
            cpu.reg_write(UC_ARM_REG_R0,value)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def run(self,entry,r0):
        self.end=False
        self.cpu.reg_write(UC_ARM_REG_R0,r0)
        self.cpu.reg_write(UC_ARM_REG_SP,0x20020000)
        self.cpu.reg_write(UC_ARM_REG_LR,RETURN|1)
        self.cpu.emu_start(entry|1,0,count=1000)
        assert self.end, hex(self.cpu.reg_read(UC_ARM_REG_PC))
        return self.cpu.reg_read(UC_ARM_REG_R0)
    def press(self,key=0x7e04,down=True):
        self.key=key
        self.w(EVENT+5,int(down),1)
        return self.run(0x08022bd4,EVENT)
    def draw(self):
        self.run(0x0802279c,0)

h=Harness()
assert h.press()==0 and h.r(MODE)==2 and h.calls==[]
h.draw()
assert h.r(MODE)==0 and h.r(CURRENT,2)==1
assert h.calls[:2]==[('open',1),('frame',1)]
h.w(FRAME_READY,0,1)
h.w(LCD_BUSY,0,1)
assert h.press(down=False)==1 and h.r(MODE)==0
assert h.press()==0
h.draw()
assert h.r(CURRENT,2)==0

for count,storage,enabled in [(0,False,True),(1,False,True),(2,True,True),(2,False,False)]:
    h=Harness(count=count,storage=storage,enabled=enabled)
    assert h.press()==0 and not h.r(MODE) and not h.calls

h=Harness()
h.w(OBJ+0x1c,0)
assert h.press()==0 and h.r(MODE)==0

h=Harness()
h.w(FRAME_READY,1,1)
h.w(LCD_BUSY,1,1)
h.press()
h.draw()
assert h.r(MODE)==2 and h.calls==[('busy',0)]
h.w(FRAME_READY,0,1)
h.w(LCD_BUSY,0,1)
h.draw()
assert h.r(MODE)==0 and h.r(CURRENT,2)==1

h=Harness(mode=1)
h.completed_frame=True
h.draw()
assert h.r(CURRENT,2)==1 and ('open',1) in h.calls and h.r(MODE)==1
h=Harness()
h.completed_frame=True
h.draw()
assert h.r(CURRENT,2)==0 and ('open',0) in h.calls
h=Harness()
assert h.press(0x7e05)==0 and h.calls==[('other_rgb',0)]
assert h.press(0x7e06)==0 and h.calls==[('other_rgb',0)]
assert h.press(0x0004)==1 and h.r(MODE)==0
print(f"Passed Thumb emulation of patched key handling and playback, including stock modes. {len(diffs)} altered payload bytes.")
