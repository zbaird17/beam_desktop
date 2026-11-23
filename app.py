import tkinter as tk

from beam_ui import BeamDesignerUI


def main():
    root = tk.Tk()
    BeamDesignerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
