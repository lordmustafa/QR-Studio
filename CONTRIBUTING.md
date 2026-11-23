# Contributing to QR Studio

Thanks for helping. Bug reports, ideas, translations and code are all welcome.

## Report a bug or ask for a feature

Open an [issue](https://github.com/lordmustafa/QR-Studio/issues/new/choose). For a bug, include:

- your system (Windows 11, macOS 15 on Apple Silicon, …) and the QR Studio version
- what you did, what you expected, and what happened
- a screenshot if the problem is visible, or the file that fails to scan

Do not paste real Wi-Fi passwords or private contact details. Use made-up ones.

## Send a change

1. Fork the repository and create a branch.
2. Set up the project as in [docs/BUILDING.md](docs/BUILDING.md).
3. Make your change. Keep it focused on one thing.
4. Run the tests:

   ```bash
   .venv/bin/python -m unittest discover tests
   ```

5. If you changed the interface, check it in Arabic and English, in light and dark, and in a
   small window.
6. Open a pull request that says what changed and why.

## Code guidelines

- Python 3.10+, standard library first. Add a dependency only when it clearly pays off.
- Logic that does not need the window goes in `qr_studio/` (payloads, renderer, exporter,
  storage), not in `qr_studio/ui/`, so it can be tested.
- Every text the user sees goes in `qr_studio/i18n.py`, in both `en` and `ar`.
- Add a test in `tests/` for new payloads, checks or export formats.

## Translations

The interface text lives in `qr_studio/i18n.py`. To add a language, copy the `en` block, translate
the values (not the keys) and add the language to `LANGUAGES`. Right-to-left languages also need
the language code added where `rtl` is decided.

## License

By contributing, you agree that your work is released under the [MIT License](LICENSE).
