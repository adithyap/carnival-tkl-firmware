# Experimental v5 display controls

This build extends the hardware-tested Next GIF patch. The five added controls use previously unused custom keycodes. The table uses free Layer 1 positions from the tested keyboard's current layout.

| Shortcut | Layer 1 assignment | Action |
| --- | --- | --- |
| Fn + F4 | `0x7E0D` | Toggle LCD and all RGB output together. |
| Fn + F5 | `0x7E0C` | Toggle the color LCD. |
| Fn + F6 | `0x7E0B` | Toggle the 5 × 5 RGB grid. |
| Fn + F7 | `0x7E0A` | Select automatic GIF rotation. |
| Fn + F8 | `0x7E09` | Toggle Vial's grid typing effect. |

The blackout controls preserve each zone's configured effect and color. Grid-only and LCD-only blackouts remain in effect when all-off is turned back on. Blackout state resets at power-up. The typing shortcut uses the same settings routine as Vial.

The previous Fn + F9 Next GIF and Fn + Backslash playback-mode controls still work in emulation. The stock RGB Mode +/− keycodes still dispatch to their original handlers. Keep them on Fn + F10 and Fn + F11 if those are your existing bindings.

## Build and verify

Run these from the package directory with the [original build dependencies](README.md#build-and-verify) installed.

```sh
python build_display_controls.py
python verify_display_controls.py
```

The candidate SHA-256 is `e3ed998c7457fd15649543c882145778aad77c4f5d9e35734eb0a5d73bd0b553`. Tests exercise the original and modified key dispatch, GIF advance and rotation, typing settings, RGB blackout and restoration, and LCD transitions around USB suspend, storage mode, and an active frame transfer. USB, physical OLED/LCD output, GPIO and LED output were not tested on a board for this build.

The previous Next GIF UF2 remains the rollback image for this build if the bootloader is accessible. Hardware recovery on a non-booting board is still unverified.
