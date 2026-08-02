from tkinter import *
from tkinter import ttk
from tkinter import filedialog, messagebox
from SaveGame import SaveGame

# The currently loaded save, shared so the UI (added later) can read/edit it.
current_save = None


def upload_save():
    """Prompt the user to select a save file via the native file picker,
    returns file path"""
    path = filedialog.askopenfilename(
        title="Upload Save File",
        filetypes=[("Save files", "*.nt"), ("All files", "*.*")],
    )
    if not path:
        return None
    return path


def load_save():
    """Prompt for a save file, load it into a SaveGame, and keep it in
    current_save for the rest of the UI to use."""
    global current_save
    path = upload_save()
    if not path:
        return None
    try:
        current_save = SaveGame(path)
    except Exception as error:
        messagebox.showerror("Failed to load save", str(error))
        return None
    status.set(
        f"Loaded {len(current_save.employees)} employees, "
        f"{len(current_save.factions)} factions"
    )
    return current_save


root = Tk()
root.title("News Tower Save Editor")
frm = ttk.Frame(root, padding=10)
frm.grid()

status = StringVar(value="No save loaded")
ttk.Label(frm, textvariable=status).grid(column=0, row=0, columnspan=2)
ttk.Button(frm, text="Upload Save", command=load_save).grid(column=0, row=1)
ttk.Button(frm, text="Quit", command=root.destroy).grid(column=1, row=1)
root.mainloop()
