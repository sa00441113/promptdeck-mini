import json
import sys
import shutil
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


APP_NAME = "PromptDeck mini"
APP_VERSION = "0.1.0"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "promptdeck-mini.json"
LORA_EXTENSIONS = {".safetensors", ".pt", ".ckpt"}
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]
PROMPT_CATEGORIES = [
    "Quality",
    "Style",
    "Lighting",
    "Camera",
    "Expression",
    "Background",
    "Negative",
    "Other",
]


def empty_data():
    return {
        "appName": APP_NAME,
        "version": APP_VERSION,
        "loraFolderPath": "",
        "excludedLoras": [],
        "loras": {},
        "prompts": [
            {
                "id": str(uuid.uuid4()),
                "title": "High quality baseline",
                "category": "Quality",
                "promptText": "masterpiece, best quality, detailed",
                "memo": "Sample prompt. Edit or delete it.",
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Soft studio light",
                "category": "Lighting",
                "promptText": "soft studio lighting, clean shadows",
                "memo": "Sample lighting snippet.",
            },
        ],
    }


def load_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        data = empty_data()
        save_data(data)
        return data
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        backup = DATA_FILE.with_suffix(".broken.json")
        shutil.copy2(DATA_FILE, backup)
        data = empty_data()
        save_data(data)
        return data
    data.setdefault("appName", APP_NAME)
    data.setdefault("version", APP_VERSION)
    data.setdefault("loraFolderPath", "")
    data.setdefault("excludedLoras", [])
    data.setdefault("loras", {})
    data.setdefault("prompts", [])
    normalize_excluded_loras(data)
    return data


def save_data(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalized_path(path):
    try:
        return str(Path(path).resolve())
    except (OSError, RuntimeError):
        return str(Path(path).absolute())


def normalize_excluded_loras(data):
    excluded = []
    seen = set()
    for item in data.setdefault("excludedLoras", []):
        if not item:
            continue
        path = normalized_path(item)
        if path not in seen:
            excluded.append(path)
            seen.add(path)
    data["excludedLoras"] = excluded


class PromptDeckMini(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1120x720")
        self.minsize(960, 620)

        self.data = load_data()
        self.lora_files = []
        self.visible_lora_files = []
        self.selected_lora_file = None
        self.selected_prompt_id = None
        self.visible_prompt_ids = []
        self.preview_photo = None

        self._setup_style()
        self._build_menu()
        self._build_ui()
        self.scan_lora_folder()
        self.refresh_prompts()

    def _setup_style(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TButton", padding=(10, 6))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", foreground="#666666")

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Import JSON", command=self.import_json)
        file_menu.add_command(label="Export JSON", command=self.export_json)
        file_menu.add_command(label="Reset Hidden LoRAs", command=self.reset_hidden_loras)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(root)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="Import JSON", command=self.import_json).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(toolbar, text="Export JSON", command=self.export_json).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.lora_tab = ttk.Frame(notebook, padding=8)
        self.prompts_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.lora_tab, text="LoRA")
        notebook.add(self.prompts_tab, text="Prompts")

        self._build_lora_tab()
        self._build_prompts_tab()

    def _build_lora_tab(self):
        self.lora_tab.columnconfigure(0, weight=2)
        self.lora_tab.columnconfigure(1, weight=2)
        self.lora_tab.columnconfigure(2, weight=3)
        self.lora_tab.rowconfigure(1, weight=1)

        top = ttk.Frame(self.lora_tab)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Button(top, text="Select LoRA Folder", command=self.select_lora_folder).grid(row=0, column=0, padx=(0, 8))
        self.lora_folder_var = tk.StringVar(value=self.data.get("loraFolderPath", ""))
        ttk.Label(top, textvariable=self.lora_folder_var, style="Muted.TLabel").grid(row=0, column=1, sticky="ew")

        left = ttk.Frame(self.lora_tab)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="LoRA List", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self.lora_search_var = tk.StringVar()
        self.lora_search_var.trace_add("write", lambda *_: self.refresh_lora_list())
        ttk.Entry(left, textvariable=self.lora_search_var).grid(row=1, column=0, sticky="ew", pady=6)
        self.lora_list = tk.Listbox(left, exportselection=False)
        self.lora_list.grid(row=2, column=0, sticky="nsew")
        self.lora_list.bind("<<ListboxSelect>>", self.on_lora_select)

        middle = ttk.Frame(self.lora_tab)
        middle.grid(row=1, column=1, sticky="nsew", padx=(0, 8))
        middle.rowconfigure(1, weight=1)
        middle.columnconfigure(0, weight=1)
        ttk.Label(middle, text="Preview", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self.preview_frame = ttk.Frame(middle, relief=tk.SOLID, borderwidth=1)
        self.preview_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 8))
        self.preview_frame.rowconfigure(0, weight=1)
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_label = ttk.Label(self.preview_frame, text="No preview", anchor=tk.CENTER)
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        ttk.Button(middle, text="Set Preview Image", command=self.set_preview_image).grid(row=2, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(middle, text="Remove Preview Image", command=self.remove_preview_image).grid(row=3, column=0, sticky="ew")

        right = ttk.Frame(self.lora_tab)
        right.grid(row=1, column=2, sticky="nsew")
        right.columnconfigure(1, weight=1)
        right.rowconfigure(8, weight=1)
        ttk.Label(right, text="LoRA Details", style="Header.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self.lora_file_var = tk.StringVar()
        self.display_name_var = tk.StringVar()
        self.trigger_var = tk.StringVar()
        self.weight_var = tk.StringVar(value="0.8")
        self.preview_path_var = tk.StringVar()
        fields = [
            ("File", self.lora_file_var, "readonly"),
            ("Display Name", self.display_name_var, "normal"),
            ("Trigger", self.trigger_var, "normal"),
            ("Weight", self.weight_var, "normal"),
            ("Preview Image", self.preview_path_var, "readonly"),
        ]
        for idx, (label, var, state) in enumerate(fields, start=1):
            ttk.Label(right, text=label).grid(row=idx, column=0, sticky="w", pady=5)
            ttk.Entry(right, textvariable=var, state=state).grid(row=idx, column=1, sticky="ew", pady=5)
        ttk.Label(right, text="Memo").grid(row=6, column=0, sticky="nw", pady=5)
        self.lora_memo = tk.Text(right, height=10, wrap=tk.WORD)
        self.lora_memo.grid(row=6, column=1, sticky="nsew", pady=5)
        buttons = ttk.Frame(right)
        buttons.grid(row=7, column=1, sticky="ew", pady=(8, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        buttons.columnconfigure(2, weight=1)
        ttk.Button(buttons, text="Save", command=self.save_lora_details).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Copy LoRA", command=self.copy_lora).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Delete LoRA Entry", command=self.delete_lora_entry).grid(row=0, column=2, sticky="ew")

    def _build_prompts_tab(self):
        self.prompts_tab.columnconfigure(0, weight=1)
        self.prompts_tab.columnconfigure(1, weight=2)
        self.prompts_tab.columnconfigure(2, weight=3)
        self.prompts_tab.rowconfigure(1, weight=1)

        top = ttk.Frame(self.prompts_tab)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        top.columnconfigure(0, weight=1)
        self.prompt_search_var = tk.StringVar()
        self.prompt_search_var.trace_add("write", lambda *_: self.refresh_prompts())
        ttk.Entry(top, textvariable=self.prompt_search_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(top, text="Add Prompt", command=self.add_prompt).grid(row=0, column=1)

        cats = ttk.Frame(self.prompts_tab)
        cats.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        cats.rowconfigure(1, weight=1)
        cats.columnconfigure(0, weight=1)
        ttk.Label(cats, text="Categories", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self.category_list = tk.Listbox(cats, exportselection=False)
        self.category_list.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        for category in ["All"] + PROMPT_CATEGORIES:
            self.category_list.insert(tk.END, category)
        self.category_list.selection_set(0)
        self.category_list.bind("<<ListboxSelect>>", lambda _e: self.refresh_prompts())

        center = ttk.Frame(self.prompts_tab)
        center.grid(row=1, column=1, sticky="nsew", padx=(0, 8))
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)
        ttk.Label(center, text="Prompt List", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self.prompt_list = tk.Listbox(center, exportselection=False)
        self.prompt_list.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.prompt_list.bind("<<ListboxSelect>>", self.on_prompt_select)

        right = ttk.Frame(self.prompts_tab)
        right.grid(row=1, column=2, sticky="nsew")
        right.columnconfigure(1, weight=1)
        right.rowconfigure(3, weight=2)
        right.rowconfigure(5, weight=1)
        ttk.Label(right, text="Prompt Details", style="Header.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self.prompt_title_var = tk.StringVar()
        self.prompt_category_var = tk.StringVar(value="Other")
        ttk.Label(right, text="Title").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(right, textvariable=self.prompt_title_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(right, text="Category").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Combobox(right, textvariable=self.prompt_category_var, values=PROMPT_CATEGORIES, state="readonly").grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(right, text="Prompt Text").grid(row=3, column=0, sticky="nw", pady=5)
        self.prompt_text = tk.Text(right, height=12, wrap=tk.WORD)
        self.prompt_text.grid(row=3, column=1, sticky="nsew", pady=5)
        ttk.Label(right, text="Memo").grid(row=5, column=0, sticky="nw", pady=5)
        self.prompt_memo = tk.Text(right, height=6, wrap=tk.WORD)
        self.prompt_memo.grid(row=5, column=1, sticky="nsew", pady=5)
        buttons = ttk.Frame(right)
        buttons.grid(row=6, column=1, sticky="ew", pady=(8, 0))
        for col in range(3):
            buttons.columnconfigure(col, weight=1)
        ttk.Button(buttons, text="Edit / Save", command=self.save_prompt).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Delete", command=self.delete_prompt).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Copy Prompt", command=self.copy_prompt).grid(row=0, column=2, sticky="ew")

    def select_lora_folder(self):
        folder = filedialog.askdirectory(title="Select LoRA Folder")
        if not folder:
            return
        self.data["loraFolderPath"] = folder
        self.lora_folder_var.set(folder)
        save_data(self.data)
        self.scan_lora_folder()

    def scan_lora_folder(self):
        folder = Path(self.data.get("loraFolderPath", ""))
        self.lora_files = []
        if folder.exists() and folder.is_dir():
            excluded = set(self.data.setdefault("excludedLoras", []))
            self.lora_files = sorted(
                [
                    p
                    for p in folder.iterdir()
                    if p.is_file()
                    and p.suffix.lower() in LORA_EXTENSIONS
                    and normalized_path(p) not in excluded
                ],
                key=lambda p: p.name.lower(),
            )
            for path in self.lora_files:
                self.ensure_lora_record(path)
        self.refresh_lora_list()

    def ensure_lora_record(self, path):
        file_name = path.name
        loras = self.data.setdefault("loras", {})
        record = loras.setdefault(file_name, {})
        record.setdefault("fileName", file_name)
        record.setdefault("displayName", path.stem)
        record.setdefault("trigger", "")
        record.setdefault("weight", "0.8")
        record.setdefault("memo", "")
        record.setdefault("previewImagePath", "")
        if not record.get("previewImagePath"):
            image = self.find_matching_image(path)
            if image:
                record["previewImagePath"] = str(image)

    def find_matching_image(self, lora_path):
        for ext in IMAGE_EXTENSIONS:
            candidate = lora_path.with_suffix(ext)
            if candidate.exists():
                return candidate
        return None

    def refresh_lora_list(self):
        query = self.lora_search_var.get().strip().lower() if hasattr(self, "lora_search_var") else ""
        self.lora_list.delete(0, tk.END)
        self.visible_lora_files = []
        for path in self.lora_files:
            record = self.data.get("loras", {}).get(path.name, {})
            haystack = " ".join(
                [
                    path.name,
                    record.get("displayName", ""),
                    record.get("trigger", ""),
                    record.get("memo", ""),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            label = record.get("displayName") or path.stem
            self.visible_lora_files.append(path.name)
            self.lora_list.insert(tk.END, f"{label}  ({path.name})")
        if self.lora_list.size() and not self.selected_lora_file:
            self.lora_list.selection_set(0)
            self.on_lora_select(None)
        if not self.lora_list.size():
            self.clear_lora_details()

    def on_lora_select(self, _event):
        selection = self.lora_list.curselection()
        if not selection:
            return
        file_name = self.visible_lora_files[selection[0]]
        self.selected_lora_file = file_name
        record = self.data["loras"].get(file_name, {})
        self.lora_file_var.set(record.get("fileName", file_name))
        self.display_name_var.set(record.get("displayName", Path(file_name).stem))
        self.trigger_var.set(record.get("trigger", ""))
        self.weight_var.set(str(record.get("weight", "0.8")))
        self.preview_path_var.set(record.get("previewImagePath", ""))
        self.lora_memo.delete("1.0", tk.END)
        self.lora_memo.insert("1.0", record.get("memo", ""))
        self.show_preview(record.get("previewImagePath", ""))

    def show_preview(self, image_path):
        self.preview_photo = None
        if not image_path:
            self.preview_label.configure(image="", text="No preview")
            return
        path = Path(image_path)
        if not path.exists():
            self.preview_label.configure(image="", text="Preview image not found")
            return
        if Image and ImageTk:
            try:
                image = Image.open(path)
                image.thumbnail((360, 420))
                self.preview_photo = ImageTk.PhotoImage(image)
                self.preview_label.configure(image=self.preview_photo, text="")
                return
            except OSError:
                pass
        try:
            photo = tk.PhotoImage(file=str(path))
            width = max(photo.width(), 1)
            height = max(photo.height(), 1)
            factor = max(width // 360, height // 420, 1)
            if factor > 1:
                photo = photo.subsample(factor, factor)
            self.preview_photo = photo
            self.preview_label.configure(image=self.preview_photo, text="")
            return
        except tk.TclError:
            pass
        self.preview_label.configure(image="", text=path.name)

    def selected_lora_path(self):
        if not self.selected_lora_file:
            return None
        for path in self.lora_files:
            if path.name == self.selected_lora_file:
                return path
        folder = Path(self.data.get("loraFolderPath", ""))
        if folder:
            return folder / self.selected_lora_file
        return Path(self.selected_lora_file)

    def clear_lora_details(self):
        self.selected_lora_file = None
        self.lora_file_var.set("")
        self.display_name_var.set("")
        self.trigger_var.set("")
        self.weight_var.set("0.8")
        self.preview_path_var.set("")
        self.lora_memo.delete("1.0", tk.END)
        self.show_preview("")

    def save_lora_details(self):
        if not self.selected_lora_file:
            messagebox.showinfo(APP_NAME, "Select a LoRA first.")
            return
        record = self.data.setdefault("loras", {}).setdefault(self.selected_lora_file, {})
        record["fileName"] = self.selected_lora_file
        record["displayName"] = self.display_name_var.get().strip() or Path(self.selected_lora_file).stem
        record["trigger"] = self.trigger_var.get().strip()
        record["weight"] = self.weight_var.get().strip() or "0.8"
        record["memo"] = self.lora_memo.get("1.0", tk.END).strip()
        record["previewImagePath"] = self.preview_path_var.get().strip()
        save_data(self.data)
        self.refresh_lora_list()
        messagebox.showinfo(APP_NAME, "LoRA saved.")

    def set_preview_image(self):
        if not self.selected_lora_file:
            messagebox.showinfo(APP_NAME, "Select a LoRA first.")
            return
        filetypes = [("Image files", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Set Preview Image", filetypes=filetypes)
        if not path:
            return
        self.preview_path_var.set(path)
        self.show_preview(path)
        self.save_lora_details()

    def remove_preview_image(self):
        if not self.selected_lora_file:
            messagebox.showinfo(APP_NAME, "Select a LoRA first.")
            return
        self.preview_path_var.set("")
        self.show_preview("")
        self.save_lora_details()

    def delete_lora_entry(self):
        if not self.selected_lora_file:
            messagebox.showinfo(APP_NAME, "Select a LoRA first.")
            return
        if not messagebox.askokcancel(
            APP_NAME,
            "Delete this LoRA entry from PromptDeck mini?\nThis will not delete the actual LoRA file.",
        ):
            return
        lora_path = self.selected_lora_path()
        if lora_path:
            excluded = self.data.setdefault("excludedLoras", [])
            excluded_path = normalized_path(lora_path)
            if excluded_path not in excluded:
                excluded.append(excluded_path)
        self.data.setdefault("loras", {}).pop(self.selected_lora_file, None)
        self.lora_files = [path for path in self.lora_files if path.name != self.selected_lora_file]
        save_data(self.data)
        self.clear_lora_details()
        self.refresh_lora_list()

    def reset_hidden_loras(self):
        hidden_count = len(self.data.get("excludedLoras", []))
        if not hidden_count:
            messagebox.showinfo(APP_NAME, "No hidden LoRAs to reset.")
            return
        if not messagebox.askyesno(APP_NAME, "Show all hidden LoRA entries again?"):
            return
        self.data["excludedLoras"] = []
        save_data(self.data)
        self.selected_lora_file = None
        self.scan_lora_folder()
        messagebox.showinfo(APP_NAME, "Hidden LoRAs reset.")

    def copy_lora(self):
        if not self.selected_lora_file:
            messagebox.showinfo(APP_NAME, "Select a LoRA first.")
            return
        lora_name = Path(self.selected_lora_file).stem
        weight = self.weight_var.get().strip() or "0.8"
        trigger = self.trigger_var.get().strip()
        text = f"[lora:{lora_name}:{weight}](lora:{lora_name}:{weight})"
        if trigger:
            text = f"{text}, {trigger}"
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def current_category(self):
        selection = self.category_list.curselection()
        if not selection:
            return "All"
        return self.category_list.get(selection[0])

    def refresh_prompts(self):
        if not hasattr(self, "prompt_list"):
            return
        category = self.current_category()
        query = self.prompt_search_var.get().strip().lower()
        self.prompt_list.delete(0, tk.END)
        self.visible_prompt_ids = []
        for prompt in self.data.get("prompts", []):
            if category != "All" and prompt.get("category") != category:
                continue
            haystack = " ".join(
                [
                    prompt.get("title", ""),
                    prompt.get("category", ""),
                    prompt.get("promptText", ""),
                    prompt.get("memo", ""),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            self.visible_prompt_ids.append(prompt.get("id"))
            self.prompt_list.insert(tk.END, f"{prompt.get('title', 'Untitled')}  [{prompt.get('category', 'Other')}]")

    def prompt_from_id(self, prompt_id):
        for prompt in self.data.get("prompts", []):
            if prompt.get("id") == prompt_id:
                return prompt
        return None

    def on_prompt_select(self, _event):
        selection = self.prompt_list.curselection()
        if not selection:
            return
        prompt = self.prompt_from_id(self.visible_prompt_ids[selection[0]])
        if not prompt:
            return
        self.selected_prompt_id = prompt.get("id")
        self.prompt_title_var.set(prompt.get("title", ""))
        self.prompt_category_var.set(prompt.get("category", "Other"))
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", prompt.get("promptText", ""))
        self.prompt_memo.delete("1.0", tk.END)
        self.prompt_memo.insert("1.0", prompt.get("memo", ""))

    def add_prompt(self):
        prompt = {
            "id": str(uuid.uuid4()),
            "title": "New Prompt",
            "category": "Other",
            "promptText": "",
            "memo": "",
        }
        self.data.setdefault("prompts", []).append(prompt)
        self.selected_prompt_id = prompt["id"]
        save_data(self.data)
        self.refresh_prompts()
        self.prompt_title_var.set(prompt["title"])
        self.prompt_category_var.set(prompt["category"])
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_memo.delete("1.0", tk.END)

    def save_prompt(self):
        if not self.selected_prompt_id:
            self.add_prompt()
        prompt = self.find_prompt(self.selected_prompt_id)
        if not prompt:
            return
        prompt["title"] = self.prompt_title_var.get().strip() or "Untitled"
        prompt["category"] = self.prompt_category_var.get() if self.prompt_category_var.get() in PROMPT_CATEGORIES else "Other"
        prompt["promptText"] = self.prompt_text.get("1.0", tk.END).strip()
        prompt["memo"] = self.prompt_memo.get("1.0", tk.END).strip()
        save_data(self.data)
        self.refresh_prompts()
        messagebox.showinfo(APP_NAME, "Prompt saved.")

    def find_prompt(self, prompt_id):
        for prompt in self.data.get("prompts", []):
            if prompt.get("id") == prompt_id:
                return prompt
        return None

    def delete_prompt(self):
        if not self.selected_prompt_id:
            messagebox.showinfo(APP_NAME, "Select a prompt first.")
            return
        if not messagebox.askyesno(APP_NAME, "Delete this prompt?"):
            return
        self.data["prompts"] = [p for p in self.data.get("prompts", []) if p.get("id") != self.selected_prompt_id]
        self.selected_prompt_id = None
        save_data(self.data)
        self.refresh_prompts()
        self.prompt_title_var.set("")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_memo.delete("1.0", tk.END)

    def copy_prompt(self):
        text = self.prompt_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo(APP_NAME, "Prompt text is empty.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def import_json(self):
        path = filedialog.askopenfilename(title="Import JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                incoming = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"Import failed:\n{exc}")
            return
        incoming.setdefault("loraFolderPath", "")
        incoming.setdefault("excludedLoras", [])
        incoming.setdefault("loras", {})
        incoming.setdefault("prompts", [])
        normalize_excluded_loras(incoming)
        self.data = incoming
        save_data(self.data)
        self.lora_folder_var.set(self.data.get("loraFolderPath", ""))
        self.selected_lora_file = None
        self.selected_prompt_id = None
        self.scan_lora_folder()
        self.refresh_prompts()
        messagebox.showinfo(APP_NAME, "JSON imported.")

    def export_json(self):
        path = filedialog.asksaveasfilename(
            title="Export JSON",
            defaultextension=".json",
            initialfile="promptdeck-mini.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        save_data(self.data)
        try:
            shutil.copy2(DATA_FILE, path)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Export failed:\n{exc}")
            return
        messagebox.showinfo(APP_NAME, "JSON exported.")


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        data = load_data()
        print(f"{APP_NAME} smoke ok: {len(data.get('prompts', []))} prompt(s)")
        raise SystemExit(0)
    app = PromptDeckMini()
    app.mainloop()
