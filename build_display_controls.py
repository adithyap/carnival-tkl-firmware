"""Build the expanded Carnival TKL v5 display controls."""
from hashlib import sha256
import struct

from build_gif_patch import (
    BASE, ROOT, KEY_CODE, KEY_HOOK, assemble, apply_patch,
    flash_offset, stock_image, wide_branch,
)

CANDIDATE = ROOT / "Carnival-TKL-v5-Display-Controls-experimental.uf2"
STATE = 0x2000058C
BSS_START_LITERAL = 0x080222E8
KEY_STUB = 0x0803E100
LCD_POWER_STUB = 0x0803E240
LCD_TICK_STUB = 0x0803E280
GRID_STUB = 0x0803E380
RGB_STUB = 0x0803E3C0

# Keycodes and locations as seen on a current Carnival TKL keymap.
BINDINGS = {
    "Fn + F4": (0, 5, 0x7E0D, "All displays and lights off / restore"),
    "Fn + F5": (0, 6, 0x7E0C, "LCD off / restore"),
    "Fn + F6": (0, 7, 0x7E0B, "RGB grid off / restore"),
    "Fn + F7": (0, 8, 0x7E0A, "Select automatic GIF rotation"),
    "Fn + F8": (0, 9, 0x7E09, "Toggle grid typing effect"),
}

def build():
    stock, payload = stock_image()
    image = bytearray(apply_patch(payload))

    def replace(at, before, after):
        i = flash_offset(at)
        assert len(before) == len(after)
        assert image[i:i+len(before)] == before, hex(at)
        image[i:i+len(after)] = after

    def install(at, limit, source):
        code = assemble(source, at)
        assert at + len(code) <= limit
        replace(at, bytes(len(code)), code)

    # The word immediately after .data and before the original .bss is
    # alignment padding. Clear it with .bss at boot. No heap or stack changes.
    replace(BSS_START_LITERAL, struct.pack("<I", STATE+4), struct.pack("<I", STATE))

    # Preserve the prior Next GIF dispatcher for 0x7e04 and all stock
    # behavior for unrecognized codes. The stock handler gets here on down
    # events only, after handling the standard RGB mode +/- actions.
    replace(KEY_HOOK, wide_branch(KEY_HOOK, KEY_CODE), wide_branch(KEY_HOOK, KEY_STUB))
    install(KEY_STUB, LCD_POWER_STUB, """
        movw r3, #0x7e09
        subs.w r3, r4, r3
        cmp r3, #4
        bhi stock_key
        cbz r3, typing
        cmp r3, #1
        beq cycle
        cmp r3, #2
        beq grid
        cmp r3, #3
        beq lcd
        movs r2, #4
        b toggle_lcd
    lcd:
        movs r2, #1
    toggle_lcd:
        movw r1, #0x058c
        movt r1, #0x2000
        ldrb r3, [r1]
        eors r3, r2
        orr r3, r3, #8
        strb r3, [r1]
        b consume
    grid:
        movw r1, #0x058c
        movt r1, #0x2000
        ldrb r3, [r1]
        eor r3, r3, #2
        strb r3, [r1]
        b consume
    cycle:
        movs r0, #1
        bl #0x080227d8
        b consume
    typing:
        sub sp, #16
        movs r3, #0
        str r3, [sp]
        str r3, [sp, #4]
        str r3, [sp, #8]
        str r3, [sp, #12]
        movs r0, #0
        mov r1, sp
        bl #0x080256cc
        cbz r0, typing_done
        ldrb.w r3, [sp]
        eor r3, r3, #0x80
        strb.w r3, [sp]
        movs r0, #0
        mov r1, sp
        bl #0x08025710
    typing_done:
        add sp, #16
    consume:
        b.w #0x08022c4c
    stock_key:
        b.w #0x0803e000
    """)

    # Screen enable is filtered at the stock on/off setter. LCD-only and
    # all-off are independent, and a USB resume cannot override either.
    replace(0x080227F4, bytes.fromhex("044a1378"), wide_branch(0x080227F4, LCD_POWER_STUB))
    install(LCD_POWER_STUB, LCD_TICK_STUB, """
        movw r2, #0x058c
        movt r2, #0x2000
        ldrb r3, [r2]
        tst r3, #5
        it ne
        movne r0, #0
        movw r2, #0x0240
        movt r2, #0x2000
        ldrb r3, [r2]
        b.w #0x080227f8
    """)

    # Process a key-requested LCD transition in the screen task, after
    # the stock storage-mode gate. Wait for any active LCD transfer.
    replace(0x080227A8, bytes.fromhex("084b1b78"), wide_branch(0x080227A8, LCD_TICK_STUB))
    install(LCD_TICK_STUB, GRID_STUB, """
        movw r5, #0x058c
        movt r5, #0x2000
        ldrb r3, [r5]
        tst r3, #8
        beq stock_tick
        movw r3, #0xcb54
        movt r3, #0x2000
        ldrb r3, [r3]
        cbnz r3, stock_tick
        movw r3, #0x0815
        movt r3, #0x2000
        ldrb r3, [r3]
        cbz r3, apply
        movw r0, #0x8818
        movt r0, #0x2000
        bl #0x0802290e
        cbz r0, wait_tick
        movw r3, #0x0814
        movt r3, #0x2000
        movs r2, #0
        strh r2, [r3]
    apply:
        ldrb r3, [r5]
        bic r3, r3, #8
        strb r3, [r5]
        movs r0, #1
        bl #0x080227f4
    stock_tick:
        movw r3, #0x0240
        movt r3, #0x2000
        ldrb r3, [r3]
        b.w #0x080227ac
    wait_tick:
        b.w #0x080227c4
    """)

    # Use the existing disabled-grid draw path, which clears every dot.
    replace(0x08025442, bytes.fromhex("1578002d"), wide_branch(0x08025442, GRID_STUB))
    install(GRID_STUB, RGB_STUB, """
        ldrb r5, [r2]
        movw r3, #0x058c
        movt r3, #0x2000
        ldrb r3, [r3]
        tst r3, #2
        it ne
        movne r5, #0
        cmp r5, #0
        b.w #0x08025446
    """)

    # Feed all-off into the driver's existing suspend blackout path.
    # Keep the host's real suspend flag and the live Vial settings intact.
    replace(0x08026564, bytes.fromhex("33782060"), wide_branch(0x08026564, RGB_STUB))
    install(RGB_STUB, RGB_STUB+0x80, """
        str r0, [r4]
        movw r2, #0x058c
        movt r2, #0x2000
        ldrb r3, [r2]
        tst r3, #4
        beq stock_rgb
        b.w #0x08026576
    stock_rgb:
        ldrb r3, [r6]
        cbz r3, render_rgb
        b.w #0x08026576
    render_rgb:
        b.w #0x0802656a
    """)
    # The driver checks the suspend flag again just before each hardware
    # update. Patch that check too so the stock blank frame reaches LEDs.
    replace(0x08026586, bytes.fromhex("337823b1"), wide_branch(0x08026586, RGB_STUB+0x80))
    install(RGB_STUB+0x80, RGB_STUB+0x100, """
        movw r2, #0x058c
        movt r2, #0x2000
        ldrb r3, [r2]
        tst r3, #4
        bne set_black
        ldrb r3, [r6]
        cbz r3, commit_rgb
    set_black:
        b.w #0x0802658a
    commit_rgb:
        b.w #0x08026594
    """)

    result = bytearray(stock)
    for index in range(len(stock)//512):
        uf2_payload = index*512 + 32
        a = index*256
        result[uf2_payload:uf2_payload+256] = image[a:a+256]
    return bytes(result), bytes(image)

if __name__ == "__main__":
    uf2, _ = build()
    CANDIDATE.write_bytes(uf2)
    print(f"Display Controls candidate SHA-256 {sha256(uf2).hexdigest()}")
