import os
from tkinter import *
from tkinter import ttk
from tkinter import filedialog, messagebox
from SaveGame import SaveGame

# The currently loaded save, shared across the UI.
current_save = None
selected_employee = None
check_vars = {}            # Employee -> BooleanVar (row checkbox)

NO_CHANGE = "(no change)"
KEEP = "(keep)"

SORT_OPTIONS = ["Name (A–Z)", "Name (Z–A)", "Skill (A–Z)", "Skill (Z–A)"]


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
    """Prompt for a save file, load it into a SaveGame, and render the UI."""
    global current_save
    path = upload_save()
    if not path:
        return
    try:
        current_save = SaveGame(path)
    except Exception as error:
        messagebox.showerror("Failed to load save", str(error))
        return
    status.set(f"Loaded {len(current_save.employees)} employees, "
               f"{len(current_save.factions)} factions  —  {os.path.basename(path)}")
    global selected_employee
    selected_employee = None
    check_vars.clear()
    rebuild_employee_list()
    rebuild_bulk_panel()
    rebuild_factions()
    clear_detail()


# ---- employee list ---------------------------------------------------------

def primary_skill(emp):
    """The employee's highest-level skill (their job->skill specialization)."""
    if not emp.skills:
        return None
    return max(emp.skills, key=lambda s: (s.level or 0))


def sorted_employees():
    emps = list(current_save.employees)
    choice = sort_var.get()
    reverse = "Z–A" in choice
    if choice.startswith("Skill"):
        def key(e):
            skill = primary_skill(e)
            return (skill.name if skill else "").casefold()
    else:
        def key(e):
            return (e.name or "").casefold()
    emps.sort(key=key, reverse=reverse)
    return emps


def rebuild_employee_list():
    for child in emp_inner.winfo_children():
        child.destroy()
    for row, emp in enumerate(sorted_employees()):
        var = check_vars.get(emp)
        if var is None:
            var = BooleanVar(value=False)
            check_vars[emp] = var
        ttk.Checkbutton(emp_inner, variable=var).grid(column=0, row=row, sticky=W)
        skill = primary_skill(emp)
        skill_text = f"{skill.name} {skill.level}" if skill else "?"
        text = f"{emp.name or '(unnamed)'} — {emp.job or '?'} · {skill_text}"
        label = ttk.Label(emp_inner, text=text)
        label.grid(column=1, row=row, sticky=W, padx=(4, 0))
        label.bind("<Button-1>", lambda _e, e=emp: show_employee(e))
    emp_canvas.configure(scrollregion=emp_canvas.bbox("all"))


def checked_employees():
    return [emp for emp, var in check_vars.items() if var.get()]


# ---- per-employee detail / editor ------------------------------------------

def clear_detail():
    for child in detail.winfo_children():
        child.destroy()
    ttk.Label(detail, text="Click an employee to edit").grid(column=0, row=0, sticky=W)


def show_employee(emp):
    global selected_employee
    selected_employee = emp
    for child in detail.winfo_children():
        child.destroy()

    ttk.Label(detail, text=emp.name or "(unnamed)", font=("TkDefaultFont", 12, "bold")) \
        .grid(column=0, row=0, columnspan=2, sticky=W)
    ttk.Label(detail, text=f"Job: {emp.job or '?'}  (read-only)") \
        .grid(column=0, row=1, columnspan=2, sticky=W, pady=(0, 6))

    # Personality / Trainable dropdowns (swap or add on selection).
    _trait_dropdown(emp, "Personality", current_save.personality_options, row=2)
    _trait_dropdown(emp, "Trainable", current_save.trainable_options, row=3)

    ttk.Label(detail, text="Skills (0-5):").grid(column=0, row=4, sticky=W, pady=(6, 0))
    for i, skill in enumerate(emp.skills):
        ttk.Label(detail, text=skill.name).grid(column=0, row=5 + i, sticky=W, padx=(12, 0))
        var = IntVar(value=skill.level or 0)
        spin = ttk.Spinbox(detail, from_=0, to=5, width=4, textvariable=var)
        spin.grid(column=1, row=5 + i, sticky=W)
        var.trace_add("write", lambda *_a, s=skill, v=var: _set_skill(s, v))


def _trait_dropdown(emp, category, options, row):
    ttk.Label(detail, text=f"{category}:").grid(column=0, row=row, sticky=W)
    names = [name for name, _guid in options]
    name_to_guid = {name: guid for name, guid in options}
    current = emp.trait_by_category(category)
    var = StringVar(value=current.name if current else "")
    combo = ttk.Combobox(detail, values=names, textvariable=var, state="readonly", width=24)
    combo.grid(column=1, row=row, sticky=W)

    def on_select(_event, e=emp, c=category, m=name_to_guid, v=var):
        guid = m.get(v.get())
        if guid:
            current_save.set_trait(e, c, guid)
    combo.bind("<<ComboboxSelected>>", on_select)


def _set_skill(skill, var):
    try:
        skill.set_level(int(var.get()))
    except (TclError, ValueError):
        pass


# ---- bulk apply ------------------------------------------------------------

def rebuild_bulk_panel():
    for child in bulk.winfo_children():
        child.destroy()
    ttk.Label(bulk, text="Bulk apply to CHECKED employees:").grid(column=0, row=0, columnspan=2, sticky=W)

    ttk.Label(bulk, text="Personality:").grid(column=0, row=1, sticky=W)
    p_names = [NO_CHANGE] + [n for n, _g in current_save.personality_options]
    bulk.p_var = StringVar(value=NO_CHANGE)
    ttk.Combobox(bulk, values=p_names, textvariable=bulk.p_var, state="readonly", width=24) \
        .grid(column=1, row=1, sticky=W)

    ttk.Label(bulk, text="Trainable:").grid(column=0, row=2, sticky=W)
    t_names = [NO_CHANGE] + [n for n, _g in current_save.trainable_options]
    bulk.t_var = StringVar(value=NO_CHANGE)
    ttk.Combobox(bulk, values=t_names, textvariable=bulk.t_var, state="readonly", width=24) \
        .grid(column=1, row=2, sticky=W)

    ttk.Button(bulk, text="Apply to checked", command=apply_bulk).grid(column=1, row=3, sticky=W, pady=(4, 0))


def apply_bulk():
    targets = checked_employees()
    if not targets:
        messagebox.showinfo("Nothing selected", "Check one or more employees first.")
        return
    p_map = {n: g for n, g in current_save.personality_options}
    t_map = {n: g for n, g in current_save.trainable_options}
    p_choice, t_choice = bulk.p_var.get(), bulk.t_var.get()
    for emp in targets:
        if p_choice != NO_CHANGE:
            current_save.set_trait(emp, "Personality", p_map[p_choice])
        if t_choice != NO_CHANGE:
            current_save.set_trait(emp, "Trainable", t_map[t_choice])
    if selected_employee in targets:
        show_employee(selected_employee)
    messagebox.showinfo("Applied", f"Updated {len(targets)} employee(s).")


# ---- factions --------------------------------------------------------------

def rebuild_factions():
    for child in factions.winfo_children():
        child.destroy()
    ttk.Label(factions, text="Faction reputation:").grid(column=0, row=0, columnspan=2, sticky=W)
    for i, fac in enumerate(current_save.factions):
        ttk.Label(factions, text=fac.name or fac.assetGUID).grid(column=0, row=1 + i, sticky=W)
        var = IntVar(value=fac.reputation or 0)
        ttk.Spinbox(factions, from_=-999, to=999, width=6, textvariable=var) \
            .grid(column=1, row=1 + i, sticky=W)
        var.trace_add("write", lambda *_a, f=fac, v=var: _set_faction(f, v))


def _set_faction(fac, var):
    try:
        current_save.set_faction(fac.assetGUID, int(var.get()))
    except (TclError, ValueError, KeyError):
        pass


# ---- save ------------------------------------------------------------------

def do_save():
    if current_save is None:
        return
    name = save_name.get().strip()
    if name:
        out = name if os.path.isabs(name) else os.path.join(
            os.path.dirname(current_save.filePath), name)
    else:
        out = current_save.filePath
    try:
        written = current_save.save(out)
    except Exception as error:
        messagebox.showerror("Failed to save", str(error))
        return
    messagebox.showinfo("Saved", f"Wrote:\n{written}")


# ---- window layout ---------------------------------------------------------

root = Tk()
root.title("News Tower Save Editor")

toolbar = ttk.Frame(root, padding=8)
toolbar.grid(column=0, row=0, sticky=(W, E))
ttk.Button(toolbar, text="Upload Save", command=load_save).grid(column=0, row=0)
status = StringVar(value="No save loaded")
ttk.Label(toolbar, textvariable=status).grid(column=1, row=0, padx=8)

body = ttk.Frame(root, padding=8)
body.grid(column=0, row=1, sticky=(N, S, W, E))

# Left: scrollable employee list.
list_frame = ttk.LabelFrame(body, text="Employees", padding=4)
list_frame.grid(column=0, row=0, rowspan=2, sticky=(N, S), padx=(0, 8))

sort_bar = ttk.Frame(list_frame)
sort_bar.grid(column=0, row=0, columnspan=2, sticky=(W, E), pady=(0, 4))
ttk.Label(sort_bar, text="Sort:").grid(column=0, row=0)
sort_var = StringVar(value=SORT_OPTIONS[0])
sort_combo = ttk.Combobox(sort_bar, values=SORT_OPTIONS, textvariable=sort_var,
                          state="readonly", width=12)
sort_combo.grid(column=1, row=0, sticky=W, padx=(4, 0))
sort_combo.bind("<<ComboboxSelected>>",
                lambda _e: rebuild_employee_list() if current_save else None)

emp_canvas = Canvas(list_frame, width=320, height=420, highlightthickness=0)
emp_scroll = ttk.Scrollbar(list_frame, orient=VERTICAL, command=emp_canvas.yview)
emp_inner = ttk.Frame(emp_canvas)
emp_inner.bind("<Configure>", lambda _e: emp_canvas.configure(scrollregion=emp_canvas.bbox("all")))
emp_canvas.create_window((0, 0), window=emp_inner, anchor="nw")
emp_canvas.configure(yscrollcommand=emp_scroll.set)
emp_canvas.grid(column=0, row=1, sticky=(N, S))
emp_scroll.grid(column=1, row=1, sticky=(N, S))
emp_canvas.bind_all("<MouseWheel>", lambda e: emp_canvas.yview_scroll(int(-e.delta / 120), "units"))

# Right: detail editor (top) and factions (bottom).
detail = ttk.LabelFrame(body, text="Selected employee", padding=8)
detail.grid(column=1, row=0, sticky=(N, W, E))
factions = ttk.LabelFrame(body, text="Factions", padding=8)
factions.grid(column=1, row=1, sticky=(N, W, E), pady=(8, 0))

# Bulk + save controls.
bulk = ttk.LabelFrame(body, text="Bulk", padding=8)
bulk.grid(column=0, row=2, sticky=(W, E), pady=(8, 0))

save_frame = ttk.Frame(body, padding=(0, 8, 0, 0))
save_frame.grid(column=1, row=2, sticky=(W, E))
ttk.Button(save_frame, text="Save", command=do_save).grid(column=0, row=0)
ttk.Label(save_frame, text="filename (optional):").grid(column=1, row=0, padx=(8, 4))
save_name = StringVar(value="")
ttk.Entry(save_frame, textvariable=save_name, width=28).grid(column=2, row=0)

clear_detail()

if __name__ == "__main__":
    root.mainloop()
