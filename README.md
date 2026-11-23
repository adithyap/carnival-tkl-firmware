# Matrix Lab Carnival TKL v5 · Next GIF

This binary patch adds manual LCD animation switching to the Carnival TKL running Matrix Lab's `f80_v5.uf2`. Assign **RGB Next** (`0x7E04`) to **F9 on Layer 1** in Matrix Lab's Vial configurator. Hold the Fn key immediately left of the arrow cluster and tap F9 to advance one saved `.CRS` clip and loop it. Fn + Backslash still switches between single-clip playback and automatic rotation.

This patch targets the standard Carnival TKL v5 firmware. Matrix Lab lists separate firmware for the Carnival TKL RGB and AUX boards. [Matrix Lab firmware downloads](https://docs.iatkb.com/gao-su-di-yan-shi-pcb2.html)

See [Experimental v5 display controls](DISPLAY_CONTROLS.md) for the follow-up build with typing, rotation, and blackout shortcuts.

## Files

| File | Purpose |
| --- | --- |
| `build_gif_patch.py` | Builds the patched UF2 from the included stock UF2. Contains the ARM Thumb patch. |
| `verify_gif_patch.py` | Validates the changed regions and tests key handling and playback logic in emulation. |
| `flash_verified_candidate.py` | macOS flasher that checks the image hash, USB device identity, port, and boot volume before copying. |
| `Carnival-TKL-v5-Next-GIF-experimental.uf2` | Experimental build tested on the Carnival TKL. |
| `stock-Carnival-TKL-v5.uf2` | Matrix Lab's original v5 image for rollback. |

## Build and verify

Run these from the directory containing this README with Python 3 and a Clang toolchain that supports Cortex-M4. On macOS, the Xcode Command Line Tools provide Clang.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python build_gif_patch.py
python verify_gif_patch.py
```

| Image | SHA-256 |
| --- | --- |
| Experimental | `ae83a327c89c90e92f886a0954b49372ab0a1666593f74614316384057973bb2` |
| Stock | `73418e9ffb78f243892fcf7db735f7f76a000c0b2b311409b2c22d45afcd2a05` |

## Flash from macOS

Back up your layout, macros, lighting settings, and animations first. The test flash reset the keyboard's settings, which were restored from local backups. An independent hardware recovery procedure has yet to be verified on the tested PCB. The original UF2 can be used for rollback if the bootloader is accessible.

1. With the keyboard in normal mode, identify its `locationID` using `ioreg -p IOUSB -w0 -l`. Keep it connected to that USB port.
2. Use the Carnival's bootloader shortcut. On the tested keymap this is **Fn + Caps Lock**. Wait for the `BOOT` volume.
3. Run `python3 flash_verified_candidate.py --location-id 0x01122000`, substituting the location ID observed in step 1.
4. Leave the keyboard connected until it reboots. Restore your bindings as needed and test Fn + F9 with at least two valid animations loaded.
