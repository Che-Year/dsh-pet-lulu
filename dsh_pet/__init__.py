"""dsh_pet - a cute capybara desktop pet for DeepSeek Harness (dsh).

Two rendering backends are provided:

* ``ansi`` (default): truecolor half-block rendering directly in the
  terminal, using only the standard library plus Pillow when the bundled
  sprites are available.
* ``tk``: a small Tkinter window with mouse interaction (``--gui``).

The pet ships with two sprite packs taken from open-source projects (see
``assets/SOURCES.md`` for attribution and licenses):

* ``lulu``      - czy666chen/lulu (MIT)
* ``capybara``  - srwang0506/HatchPet-CapybaraLulu (Apache-2.0)
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
