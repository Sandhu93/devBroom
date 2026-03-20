from __future__ import annotations

from .settings import load_settings
from .ui import DevBroomApp


def main() -> None:
    app = DevBroomApp(settings=load_settings())
    app.mainloop()
