# Carnival TKL firmware handoff

## Current state

- The target is the standard Matrix Lab Carnival TKL running stock-derived v5 firmware, USB `4d58:1587`. The chip was identified from a board photo as a Geehy APM32F405RGT6. Keep the original UF2 family tag even though it identifies STM32F401. It is part of the working vendor image format.
- The current hardware-tested image is `Carnival-TKL-v5-Display-Controls-experimental.uf2` with SHA-256 `e3ed998c7457fd15649543c882145778aad77c4f5d9e35734eb0a5d73bd0b553`. It is built from the verified original `stock-Carnival-TKL-v5.uf2`.
- The owner confirmed the three blackout shortcuts, automatic GIF rotation, and typed-character display on the physical keyboard. The earlier Next GIF build was also tested on the same board.
- `Carnival-TKL-Display-Controls.vil` contains the current four-layer keymap and layout options. Macro trigger bindings are included. Personal macro text, animation files, and lighting settings are stored separately.
- Fn is the bottom-row key immediately left of the left arrow. See [DISPLAY_CONTROLS.md](DISPLAY_CONTROLS.md) for the key assignments. Fn + F9 advances a GIF, Fn + F10/F11 cycle RGB effects, and Fn + Backspace opens LCD storage.

## Build and verify

1. Use Python 3 plus a Clang toolchain targeting Cortex-M4. Install the Python packages from `requirements.txt` in a virtual environment.
2. Run `python build_display_controls.py` and `python verify_display_controls.py` from the repo root. The latter also exercises the earlier Next GIF paths.
3. Keep the stock image hash check and byte-shape assertions. Re-run emulation and check the UF2 block addresses and metadata whenever a patch changes. Preserve the existing USB identity, keymap semantics, and stock fallbacks.

## Before flashing

- Get the owner's explicit approval for each new firmware image. Independent hardware recovery has yet to be verified. The previous Next GIF UF2 and the stock v5 UF2 are rollback images when the bootloader is accessible.
- Back up the live keymap, macro buffer, layout options, RGB settings, and any media that matters. Previous flashes reset saved settings, so read them back after restoring.
- Record the Carnival USB location in normal mode. After **Fn + Caps Lock**, verify that the `BOOT` volume corresponds to the same USB location and bootloader USB ID `4d58:4266`. Verify the exact image hash before writing. The included `flash_verified_candidate.py` targets the earlier **Next GIF** build.
- Confirm the keyboard reconnects after flashing, restore the saved data, and verify the keymap by reading it back. Ask the owner to confirm physical LCD and lighting behavior.
- Use Matrix Lab's Vial for firmware-specific assignments. VIA reads the board through its V2 definition and can write legacy codes for newer firmware functions. Connect through one configurator at a time.
