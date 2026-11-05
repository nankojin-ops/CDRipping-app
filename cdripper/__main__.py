"""Package main entry point."""
import tkinter as tk
from cdripper.ui.presenter import CDRipperPresenter
from cdripper.ui.app_view import CDRipperAppView, set_high_dpi_awareness


def main():
    set_high_dpi_awareness()
    root = tk.Tk()
    presenter = CDRipperPresenter()
    app = CDRipperAppView(root, presenter)
    root.mainloop()


if __name__ == "__main__":
    main()