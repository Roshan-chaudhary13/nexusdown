#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BSE & NSE Extranet Downloader Platform
======================================
A premium, modern dark-themed desktop GUI app that loads, edits, 
and persists credentials, date, and save path from config.json, 
and executes the downloader scripts (BSE or NSE segments) in a 
separate thread, streaming all terminal logs live to a built-in 
terminal display.
"""

import sys
import os
import json
import time
import queue
import calendar
import threading
import importlib
from pathlib import Path
from datetime import datetime, timedelta

import webbrowser
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Frozen path helper ─────────────────────────────────────────────────────────
def get_script_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path

SCRIPT_DIR = get_script_dir()

# ── Load config ───────────────────────────────────────────────────────────────
def get_config_path():
    path = SCRIPT_DIR / "config.json"
    if not path.exists() and SCRIPT_DIR.name == "dist":
        parent_path = SCRIPT_DIR.parent / "config.json"
        if parent_path.exists():
            return parent_path
    return path

def load_config():
    config_path = get_config_path()
    if not config_path.exists():
        # Clean default blueprint
        default_config = {
            "config": {
                "Extraction_Modes": {
                    "CM": "Custom",
                    "FO": "Custom",
                    "CDS": "Custom",
                    "SLB": "Custom"
                },
                "Dates": {
                    "Capital_Dates": {
                        "FromDate": datetime.today().strftime("%d%m%Y")
                    }
                },
                "BSE_WEBEXTRANET": {
                    "URL": "https://member.bseindia.com/",
                    "Member_ID": "",
                    "User_ID": "",
                    "User_Password": "",
                    "MainFolder": "EQ",
                    "SubFolder": "Transaction"
                },
                "API_DETAILS": {
                    "NSE_API": {
                        "MemberCode": "",
                        "LoginID": "",
                        "Password": "",
                        "version": "2.0",
                        "LoginURL": "https://www.connect2nse.com/extranet-api/login/#version#",
                        "LogoutURL": "https://www.connect2nse.com/extranet-api/logout/#version#",
                        "Member_File_Download_Url": "https://www.connect2nse.com/extranet-api/member/file/download/#version#?",
                        "Common_File_Download_Url": "https://www.connect2nse.com/extranet-api/common/file/download/#version#?",
                        "Member_File_Get_Url": "https://www.connect2nse.com/extranet-api/member/content/#version#?",
                        "Common_File_Get_Url": "https://www.connect2nse.com/extranet-api/common/content/#version#?",
                        "Path_CM_Member": ["Onlinebackup", "Reports/Standard report", "Reports"],
                        "Path_CM_Common": ["bhavcopy", "varrate", "ntneat", "", "clearing"],
                        "Path_FO_Member": ["Onlinebackup", "Reports", "Reports/Standard report", "/Reports/Dnld/PNL01"],
                        "Path_FO_Common": ["Bhavcopy", "", "MarketReports", "Contracts"]
                    }
                },
                "Path": {
                    "Equity": {
                        "BSECM": str(SCRIPT_DIR / "downloads"),
                        "NSECM": "C:\\FILE\\CASH\\"
                      },
                    "FO": {
                        "NSEFO": "C:\\FILE\\NSEFO\\"
                      },
                    "CDS": {
                        "NSECD": "C:\\FILE\\NSECD\\"
                      },
                    "SLB": {
                        "NSESLB": "C:\\FILE\\NSESLB\\"
                      }
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        return default_config

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config_data):
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

# ── Thread-safe console log queue ──────────────────────────────────────────────
log_queue = queue.Queue()

class GUIConsoleWriter:
    def __init__(self, q):
        self.queue = q
    def write(self, string):
        self.queue.put(string)
    def flush(self):
        pass

# ── Custom Dark Theme Calendar Picker Dialog ──────────────────────────────────
# ── Custom Dark Theme Calendar Picker Dialog ──────────────────────────────────
class CalendarDialog(tk.Toplevel):
    def __init__(self, parent, callback, current_date_str=""):
        super().__init__(parent)
        self.callback = callback
        self.title("Select Date")
        self.geometry("290x320")
        self.resizable(False, False)
        
        # Color palettes from parent app config or dynamic
        self.theme_mode = getattr(parent, "theme_mode", "dark")
        if self.theme_mode == "dark":
            self.bg_color = "#121212"
            self.card_color = "#1e1e1e"
            self.text_color = "#ffffff"
            self.primary_teal = "#00f5d4"
            self.primary_purple = "#a78bfa"
            self.neon_yellow = "#ffe600"
        else:
            self.bg_color = "#f3f4f6"
            self.card_color = "#ffffff"
            self.text_color = "#000000"
            self.primary_teal = "#0056b3"
            self.primary_purple = "#701a75"
            self.neon_yellow = "#f1c40f"
            
        self.configure(bg=self.bg_color)
        
        # Center dialog relative to parent
        self.transient(parent)
        self.grab_set()
        
        # Position near parent
        x = parent.winfo_rootx() + 100
        y = parent.winfo_rooty() + 100
        self.geometry(f"+{x}+{y}")
        
        # Parse current date or default to today
        try:
            current_date = datetime.strptime(current_date_str, "%d-%m-%Y")
        except ValueError:
            current_date = datetime.today()
            
        self.year = current_date.year
        self.month = current_date.month
        self.selected_day = current_date.day
        
        # Header controls
        header = tk.Frame(self, bg=self.bg_color, pady=10)
        header.pack(fill="x")
        
        prev_btn = tk.Button(
            header, text="◀", bg=self.neon_yellow, fg="#000000", bd=3, relief="raised",
            font=("Segoe UI", 10, "bold"), activebackground=self.primary_teal, 
            activeforeground="#000000", cursor="hand2", padx=8, pady=3,
            command=self.prev_month
        )
        prev_btn.pack(side="left", padx=10)
        
        self.label = tk.Label(header, text="", bg=self.bg_color, fg=self.text_color, font=("Segoe UI", 11, "bold"))
        self.label.pack(side="left", fill="x", expand=True)
        
        next_btn = tk.Button(
            header, text="▶", bg=self.neon_yellow, fg="#000000", bd=3, relief="raised",
            font=("Segoe UI", 10, "bold"), activebackground=self.primary_teal, 
            activeforeground="#000000", cursor="hand2", padx=8, pady=3,
            command=self.next_month
        )
        next_btn.pack(side="right", padx=10)
        
        # Day Names header
        days_frame = tk.Frame(self, bg=self.bg_color)
        days_frame.pack(fill="x", padx=10, pady=(5, 5))
        
        for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            lbl = tk.Label(days_frame, text=d, bg=self.bg_color, fg=self.primary_teal, font=("Segoe UI", 9, "bold"), width=4)
            lbl.pack(side="left", fill="x", expand=True)
            
        # Day grid container
        self.grid_frame = tk.Frame(self, bg=self.bg_color)
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.draw_calendar()
        
    def draw_calendar(self):
        # Clear existing grid
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
            
        # Update Header label
        month_name = calendar.month_name[self.month]
        self.label.config(text=f"{month_name} {self.year}")
        
        # Generate calendar days list
        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(self.year, self.month)
        
        for week in weeks:
            row_frame = tk.Frame(self.grid_frame, bg=self.bg_color)
            row_frame.pack(fill="x")
            for day in week:
                if day == 0:
                    lbl = tk.Label(row_frame, text="", bg=self.bg_color, width=4, height=1)
                    lbl.pack(side="left", fill="x", expand=True)
                else:
                    is_selected = (day == self.selected_day)
                    bg = self.primary_teal if is_selected else self.card_color
                    fg = "#000000" if (is_selected or self.theme_mode == "light") else "#ffffff"
                    
                    btn = tk.Button(
                        row_frame, 
                        text=str(day), 
                        bg=bg, 
                        fg=fg, 
                        activebackground=self.neon_yellow if is_selected else self.primary_purple, 
                        activeforeground="#ffffff" if (not is_selected and self.theme_mode == "light") else "#000000",
                        bd=3, 
                        relief="sunken" if is_selected else "raised",
                        font=("Segoe UI", 9, "bold" if is_selected else "normal"), 
                        width=4,
                        cursor="hand2",
                        command=lambda d=day: self.select_day(d)
                    )
                    btn.pack(side="left", fill="x", expand=True, padx=1, pady=1)
                    
    def prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self.selected_day = 1
        self.draw_calendar()
        
    def next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self.selected_day = 1
        self.draw_calendar()
        
    def select_day(self, day):
        date_str = f"{day:02d}-{self.month:02d}-{self.year}"
        self.callback(date_str)
        self.destroy()

# ── Main GUI Application ───────────────────────────────────────────────────────
class BSEDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NexusDown - BSE & NSE Extranet Downloader Platform")
        self.root.geometry("880x760")
        self.root.minsize(840, 700)
        
        # Load and set window icon
        try:
            icon_path = get_resource_path("TRANSPARENT LOGO.png")
            if not icon_path.exists():
                icon_path = get_resource_path("LOGO.png")
            if icon_path.exists():
                img = Image.open(icon_path)
                self.icon_photo_root = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self.icon_photo_root)
        except Exception as e:
            print(f"Error setting window icon: {e}")
        
        # Load configuration first
        self.config = load_config()
        
        # Get theme mode from config
        self.theme_mode = self.config.get("config", {}).get("theme", "dark")
        if self.theme_mode not in ["dark", "light"]:
            self.theme_mode = "dark"
            
        # Apply premium theme styling
        self.setup_styles()
        
        # Guarantee logs directory exists right at startup
        (SCRIPT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        
        # Initialize properties
        self.running = False
        self.old_stdout = None
        self.old_stderr = None
        self.drawer_open = False
        self.current_page = "BSE"
        
        # Build layout
        self.build_ui()
        
        # Apply theme colors programmatically to sync colors
        self.apply_theme()
        
        # Initialize queue listener
        self.root.after(100, self.poll_log_queue)

    def setup_styles(self):
        # Neo-Brutalist/Skeuomorphic Color Palette based on theme
        if self.theme_mode == "dark":
            self.bg_color = "#1e272e"        # Brushed dark steel
            self.card_color = "#2f3640"      # Carbon gray panel
            self.text_color = "#f5f6fa"      # Stark silver text
            self.text_dim = "#b2bec3"        # Silver dim text
            self.terminal_bg = "#0c0d10"     # CRT black glass
            self.terminal_fg = "#00ff66"     # CRT phosphor green
            self.btn_bg = "#353b48"          # Tactile dark steel button
            self.btn_fg = "#f5f6fa"
            self.btn_active_bg = "#718093"
            self.btn_active_fg = "#ffffff"
            self.primary_teal = "#00a8ff"    # Royal Blue/Teal Accent
            self.primary_purple = "#9c88ff"  # Amethyst Purple Accent
            self.accent_btn_fg = "#000000"
        else:
            self.bg_color = "#dcdde1"        # Brushed aluminium grey
            self.card_color = "#f5f6fa"      # Polished white metal
            self.text_color = "#2f3640"      # Dark steel text
            self.text_dim = "#718093"        # Slate grey dim text
            self.terminal_bg = "#15171c"     # CRT dark glass screen
            self.terminal_fg = "#ffb000"     # CRT phosphor amber
            self.btn_bg = "#e2e8f0"          # Tactile light grey button
            self.btn_fg = "#2f3640"
            self.btn_active_bg = "#cbd5e1"
            self.btn_active_fg = "#000000"
            self.primary_teal = "#0066cc"    # Dark blue/teal for readability
            self.primary_purple = "#7b2cbf"  # Rich purple for readability
            self.accent_btn_fg = "#ffffff"

        self.input_bg = "#ffffff"        # High-contrast white background for text fields
        self.success_green = "#39ff14"   # Neon Green
        self.error_red = "#e84118"       # Tactile red
        self.terminal_bg_dark = "#000000" # fallback dark terminal color
        self.neon_yellow = "#f1c40f"     # Gold Yellow for buttons

        self.root.configure(bg=self.bg_color)
        
        # TTK styling configurations
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Customize Scrollbar in stark blocky design
        if self.theme_mode == "dark":
            self.style.configure(
                "TScrollbar",
                gripcount=0,
                background="#ffffff",
                troughcolor=self.terminal_bg,
                bordercolor="#000000",
                arrowcolor="#000000",
                lightcolor="#ffffff",
                darkcolor="#ffffff"
            )
        else:
            self.style.configure(
                "TScrollbar",
                gripcount=0,
                background="#000000",
                troughcolor="#e5e7eb",
                bordercolor="#000000",
                arrowcolor="#ffffff",
                lightcolor="#000000",
                darkcolor="#000000"
            )
        
        # Customize Combobox with high-contrast white bg and solid black borders
        self.style.configure(
            "TCombobox",
            fieldbackground="#ffffff",
            background="#ffffff",
            foreground="#000000",
            arrowcolor="#000000",
            bordercolor="#000000",
            lightcolor="#ffffff",
            darkcolor="#ffffff"
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff"), ("active", "#ffffff"), ("disabled", "#e0e0e0")],
            foreground=[("readonly", "#000000"), ("active", "#000000"), ("disabled", "#555555")]
        )

    def build_ui(self):
        # Top Header & Custom Tab Navbar container
        top_bar = tk.Frame(self.root, bg=self.bg_color)
        top_bar.pack(fill="x", pady=(15, 5), padx=20)
        
        # Branding Title Block
        brand_frame = tk.Frame(top_bar, bg=self.bg_color)
        brand_frame.pack(side="left")
        
        # Load and display logo next to the title
        logo_loaded = False
        try:
            logo_path = get_resource_path("TRANSPARENT LOGO.png")
            if not logo_path.exists():
                logo_path = get_resource_path("LOGO.png")
            if logo_path.exists():
                pil_img = Image.open(logo_path)
                h_target = 42
                w_orig, h_orig = pil_img.size
                w_target = int((w_orig / h_orig) * h_target)
                pil_img = pil_img.resize((w_target, h_target), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(pil_img)
                
                logo_lbl = tk.Label(brand_frame, image=self.logo_photo, bg=self.bg_color)
                logo_lbl.pack(side="left", padx=(0, 10))
                logo_loaded = True
        except Exception as e:
            print(f"Error loading logo: {e}")
            
        text_frame = tk.Frame(brand_frame, bg=self.bg_color)
        text_frame.pack(side="left")
        
        title_label = tk.Label(
            text_frame, 
            text="NexusDown Platform" if logo_loaded else "NEXUSDOWN PLATFORM", 
            font=("Segoe UI", 14, "bold"), 
            fg=self.primary_teal, 
            bg=self.bg_color
        )
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(
            text_frame, 
            text="BSE & NSE Extranet Downloader", 
            font=("Segoe UI", 8), 
            fg=self.text_dim, 
            bg=self.bg_color
        )
        subtitle_label.pack(anchor="w", pady=(1, 0))

        # Hamburger credentials trigger button on right
        self.hamburger_btn = tk.Button(
            top_bar,
            text="☰ Credentials Menu",
            font=("Segoe UI", 9, "bold"),
            bg=self.btn_bg,
            fg=self.btn_fg,
            activebackground=self.btn_active_bg,
            activeforeground=self.btn_active_fg,
            bd=3,
            relief="raised",
            cursor="hand2",
            padx=15,
            pady=5,
            command=self.toggle_drawer
        )
        self.hamburger_btn.pack(side="right", padx=(10, 0))

        # Contact Developer button on right
        contact_btn = tk.Button(
            top_bar,
            text="✉  Contact Developer",
            font=("Segoe UI", 9, "bold"),
            bg=self.btn_bg,
            fg=self.btn_fg,
            activebackground=self.btn_active_bg,
            activeforeground=self.btn_active_fg,
            bd=3,
            relief="raised",
            cursor="hand2",
            padx=12,
            pady=5,
            command=self.show_contact_popup
        )
        contact_btn.pack(side="right", padx=(10, 0))

        # Theme toggle button
        self.theme_btn = tk.Button(
            top_bar,
            text="☀  Light Mode" if self.theme_mode == "dark" else "🌙  Dark Mode",
            font=("Segoe UI", 9, "bold"),
            bg=self.btn_bg,
            fg=self.btn_fg,
            activebackground=self.btn_active_bg,
            activeforeground=self.btn_active_fg,
            bd=3,
            relief="raised",
            cursor="hand2",
            padx=12,
            pady=5,
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="right", padx=(10, 0))

        # Custom Tab Bar navigation
        tab_nav_frame = tk.Frame(top_bar, bg=self.bg_color)
        tab_nav_frame.pack(side="right")
        
        self.tab_bse_btn = tk.Button(
            tab_nav_frame,
            text="BSE India",
            font=("Segoe UI", 10, "bold"),
            bg=self.primary_teal,
            fg="#000000",
            activebackground=self.primary_teal,
            activeforeground="#000000",
            bd=3,
            relief="raised",
            cursor="hand2",
            padx=18,
            pady=6,
            command=lambda: self.switch_page("BSE")
        )
        self.tab_bse_btn.pack(side="left", padx=2)
        
        self.tab_nse_btn = tk.Button(
            tab_nav_frame,
            text="NSE Connect",
            font=("Segoe UI", 10, "bold"),
            bg=self.btn_bg,
            fg=self.text_color,
            activebackground=self.btn_active_bg,
            activeforeground=self.btn_active_fg,
            bd=3,
            relief="sunken",
            cursor="hand2",
            padx=18,
            pady=6,
            command=lambda: self.switch_page("NSE")
        )
        self.tab_nse_btn.pack(side="left", padx=2)

        # Main Pages View Container
        self.pages_container = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=5)
        self.pages_container.pack(fill="both", expand=True)

        # Dedicated Tab Page Container to keep settings cards at the top
        self.tab_page_container = tk.Frame(self.pages_container, bg=self.bg_color)
        self.tab_page_container.pack(fill="x", pady=(0, 5))

        # ── PAGE 1: BSE India Page ──
        self.bse_page = tk.Frame(self.tab_page_container, bg=self.bg_color)
        self.bse_page.pack(fill="both", expand=True)
        
        # Configuration Card Panel (BSE) - Tactile Raised Bevel
        config_card_bse = tk.Frame(
            self.bse_page, 
            bg=self.card_color, 
            bd=3, 
            relief="raised", 
            padx=20, 
            pady=12
        )
        config_card_bse.pack(fill="x", pady=(0, 10))
        
        card_title_bse = tk.Label(
            config_card_bse, 
            text="BSE Extranet Extraction Settings", 
            font=("Segoe UI", 11, "bold"), 
            fg=self.primary_teal, 
            bg=self.card_color
        )
        card_title_bse.pack(anchor="w", pady=(0, 10))
        
        # Drop downs
        dropdowns_frame = tk.Frame(config_card_bse, bg=self.card_color)
        dropdowns_frame.pack(fill="x", pady=(0, 5))
        
        col_cat = tk.Frame(dropdowns_frame, bg=self.card_color)
        col_cat.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(col_cat, text="Main Category (BSE Folder):", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        self.main_folder_combo = ttk.Combobox(
            col_cat, 
            values=["EQ", "FNO", "CURRENCY", "DEBT", "Commodity", "BiMF", "EGR", "GSEC", "Executable", "BSE_Approvals"],
            font=("Segoe UI", 9)
        )
        self.main_folder_combo.pack(fill="x", pady=(3, 0))
        
        col_sub = tk.Frame(dropdowns_frame, bg=self.card_color)
        col_sub.pack(side="right", fill="x", expand=True, padx=(10, 0))
        tk.Label(col_sub, text="Target Subfolder:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        self.sub_folder_combo = ttk.Combobox(
            col_sub, 
            values=["Transaction", "Common", "Dnld"],
            font=("Segoe UI", 9)
        )
        self.sub_folder_combo.pack(fill="x", pady=(3, 0))

        # Date field with calendar picker and quick-select buttons
        tk.Label(config_card_bse, text="Extraction Date (DD-MM-YYYY):", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w", pady=(5, 0))
        date_container_bse = tk.Frame(config_card_bse, bg=self.card_color)
        date_container_bse.pack(fill="x", pady=(3, 5))
        
        self.date_ent_bse = self.create_styled_entry(date_container_bse)
        self.date_ent_bse.frame.pack(side="left", fill="x", expand=True)
        
        cal_btn_bse = tk.Button(
            date_container_bse, text="📅", font=("Segoe UI", 9, "bold"),
            bg=self.neon_yellow, fg="#000000", activebackground=self.primary_teal, 
            activeforeground="#000000", bd=3, relief="raised", cursor="hand2", padx=8,
            command=lambda: self.open_calendar_picker("BSE")
        )
        cal_btn_bse.pack(side="left", padx=(5, 0))
        
        yesterday_btn_bse = tk.Button(
            date_container_bse, text="Yesterday", font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, 
            activeforeground=self.btn_active_fg, bd=3, relief="raised", cursor="hand2", padx=8, pady=2,
            command=lambda: self.set_date_to_yesterday("BSE")
        )
        yesterday_btn_bse.pack(side="left", padx=(5, 0))
        
        today_btn_bse = tk.Button(
            date_container_bse, text="Today", font=("Segoe UI", 8, "bold"),
            bg=self.primary_teal, fg=self.accent_btn_fg, activebackground=self.primary_purple, 
            activeforeground=self.accent_btn_fg, bd=3, relief="raised", cursor="hand2", padx=10, pady=2,
            command=lambda: self.set_date_to_today("BSE")
        )
        today_btn_bse.pack(side="left", padx=(5, 0))

        # Save Directory Path field (BSE)
        tk.Label(config_card_bse, text="PC Save Directory:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        path_container_bse = tk.Frame(config_card_bse, bg=self.card_color)
        path_container_bse.pack(fill="x", pady=(3, 8))
        
        self.path_ent_bse = self.create_styled_entry(path_container_bse)
        self.path_ent_bse.frame.pack(side="left", fill="x", expand=True)
        
        browse_btn_bse = tk.Button(
            path_container_bse, text="Browse...", font=("Segoe UI", 8, "bold"),
            bg=self.neon_yellow, fg="#000000", activebackground=self.primary_teal, 
            activeforeground="#000000", bd=3, relief="raised", cursor="hand2", padx=8, pady=2,
            command=lambda: self.browse_directory("BSE")
        )
        browse_btn_bse.pack(side="right", padx=(6, 0))

        # Save Settings Quick Button (BSE)
        save_settings_btn_bse = tk.Button(
            config_card_bse,
            text="💾  Save BSE Configuration",
            font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, activeforeground=self.btn_active_fg,
            bd=3, relief="raised", cursor="hand2", pady=5,
            command=lambda: self.save_settings_action("BSE")
        )
        save_settings_btn_bse.pack(fill="x")

        # ── PAGE 2: NSE Connect Page ──
        self.nse_page = tk.Frame(self.tab_page_container, bg=self.bg_color)
        
        # Configuration Card Panel (NSE) - Blocky Border
        config_card_nse = tk.Frame(
            self.nse_page, 
            bg=self.card_color, 
            highlightthickness=3, 
            highlightbackground="#000000", 
            bd=0, 
            padx=20, 
            pady=12
        )
        config_card_nse.pack(fill="x", pady=(0, 10))
        
        card_title_nse = tk.Label(
            config_card_nse, 
            text="NSE Connect2NSE API Settings", 
            font=("Segoe UI", 11, "bold"), 
            fg=self.primary_purple, 
            bg=self.card_color
        )
        card_title_nse.pack(anchor="w", pady=(0, 10))
        
        # NSE Checkboxes & Extraction Modes selection row
        segments_grid = tk.Frame(config_card_nse, bg=self.card_color)
        segments_grid.pack(fill="x", pady=(0, 8))
        
        tk.Label(segments_grid, text="Select NSE Segments & Extraction Modes:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))
        
        self.nse_cm_val = tk.BooleanVar(value=True)
        self.nse_fo_val = tk.BooleanVar(value=True)
        self.nse_cd_val = tk.BooleanVar(value=True)
        self.nse_slb_val = tk.BooleanVar(value=False)
        
        check_cm = tk.Checkbutton(segments_grid, text="Cash (CM)", variable=self.nse_cm_val, bg=self.card_color, fg=self.text_color, activebackground=self.card_color, activeforeground=self.text_color, selectcolor="#2f3640" if self.theme_mode == "dark" else "#ffffff", font=("Segoe UI", 9, "bold"))
        check_cm.grid(row=1, column=0, sticky="w", padx=(0, 15), pady=2)
        
        check_fo = tk.Checkbutton(segments_grid, text="Derivatives (FO)", variable=self.nse_fo_val, bg=self.card_color, fg=self.text_color, activebackground=self.card_color, activeforeground=self.text_color, selectcolor="#2f3640" if self.theme_mode == "dark" else "#ffffff", font=("Segoe UI", 9, "bold"))
        check_fo.grid(row=1, column=1, sticky="w", padx=15, pady=2)
        
        check_cd = tk.Checkbutton(segments_grid, text="Currency (CD)", variable=self.nse_cd_val, bg=self.card_color, fg=self.text_color, activebackground=self.card_color, activeforeground=self.text_color, selectcolor="#2f3640" if self.theme_mode == "dark" else "#ffffff", font=("Segoe UI", 9, "bold"))
        check_cd.grid(row=1, column=2, sticky="w", padx=15, pady=2)
        
        check_slb = tk.Checkbutton(segments_grid, text="SLB Reports", variable=self.nse_slb_val, bg=self.card_color, fg=self.text_color, activebackground=self.card_color, activeforeground=self.text_color, selectcolor="#2f3640" if self.theme_mode == "dark" else "#ffffff", font=("Segoe UI", 9, "bold"))
        check_slb.grid(row=1, column=3, sticky="w", padx=15, pady=2)
        
        # Toggle buttons for Modes
        self.btn_cm_mode = tk.Button(
            segments_grid, text="Custom Config", font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, bd=3, relief="raised", cursor="hand2", padx=6, pady=2,
            activebackground=self.btn_active_bg, activeforeground=self.btn_active_fg,
            command=lambda: self.toggle_mode_btn(self.btn_cm_mode)
        )
        self.btn_cm_mode.grid(row=2, column=0, sticky="we", padx=(0, 15), pady=(2, 5))
        
        self.btn_fo_mode = tk.Button(
            segments_grid, text="Custom Config", font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, bd=3, relief="raised", cursor="hand2", padx=6, pady=2,
            activebackground=self.btn_active_bg, activeforeground=self.btn_active_fg,
            command=lambda: self.toggle_mode_btn(self.btn_fo_mode)
        )
        self.btn_fo_mode.grid(row=2, column=1, sticky="we", padx=15, pady=(2, 5))
        
        self.btn_cd_mode = tk.Button(
            segments_grid, text="Custom Config", font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, bd=3, relief="raised", cursor="hand2", padx=6, pady=2,
            activebackground=self.btn_active_bg, activeforeground=self.btn_active_fg,
            command=lambda: self.toggle_mode_btn(self.btn_cd_mode)
        )
        self.btn_cd_mode.grid(row=2, column=2, sticky="we", padx=15, pady=(2, 5))
        
        self.btn_slb_mode = tk.Button(
            segments_grid, text="Custom Config", font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, bd=3, relief="raised", cursor="hand2", padx=6, pady=2,
            activebackground=self.btn_active_bg, activeforeground=self.btn_active_fg,
            command=lambda: self.toggle_mode_btn(self.btn_slb_mode)
        )
        self.btn_slb_mode.grid(row=2, column=3, sticky="we", padx=15, pady=(2, 5))
        
        def update_combos_state():
            # CM
            if self.nse_cm_val.get():
                self.btn_cm_mode.config(state="normal")
                if self.btn_cm_mode["text"] == "All Files":
                    self.btn_cm_mode.config(bg=self.primary_teal, fg=self.accent_btn_fg)
                else:
                    self.btn_cm_mode.config(bg=self.btn_bg, fg=self.btn_fg)
            else:
                self.btn_cm_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")
            # FO
            if self.nse_fo_val.get():
                self.btn_fo_mode.config(state="normal")
                if self.btn_fo_mode["text"] == "All Files":
                    self.btn_fo_mode.config(bg=self.primary_teal, fg=self.accent_btn_fg)
                else:
                    self.btn_fo_mode.config(bg=self.btn_bg, fg=self.btn_fg)
            else:
                self.btn_fo_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")
            # CD
            if self.nse_cd_val.get():
                self.btn_cd_mode.config(state="normal")
                if self.btn_cd_mode["text"] == "All Files":
                    self.btn_cd_mode.config(bg=self.primary_teal, fg=self.accent_btn_fg)
                else:
                    self.btn_cd_mode.config(bg=self.btn_bg, fg=self.btn_fg)
            else:
                self.btn_cd_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")
            # SLB
            if self.nse_slb_val.get():
                self.btn_slb_mode.config(state="normal")
                if self.btn_slb_mode["text"] == "All Files":
                    self.btn_slb_mode.config(bg=self.primary_teal, fg=self.accent_btn_fg)
                else:
                    self.btn_slb_mode.config(bg=self.btn_bg, fg=self.btn_fg)
            else:
                self.btn_slb_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")

        check_cm.config(command=update_combos_state)
        check_fo.config(command=update_combos_state)
        check_cd.config(command=update_combos_state)
        check_slb.config(command=update_combos_state)
        self.update_combos_state = update_combos_state
 
        # Date field with calendar picker (NSE)
        tk.Label(config_card_nse, text="Extraction Date (DD-MM-YYYY):", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w", pady=(5, 0))
        date_container_nse = tk.Frame(config_card_nse, bg=self.card_color)
        date_container_nse.pack(fill="x", pady=(3, 5))
        
        self.date_ent_nse = self.create_styled_entry(date_container_nse)
        self.date_ent_nse.frame.pack(side="left", fill="x", expand=True)
        
        cal_btn_nse = tk.Button(
            date_container_nse, text="📅", font=("Segoe UI", 9, "bold"),
            bg=self.neon_yellow, fg="#000000", activebackground=self.primary_teal, 
            activeforeground="#000000", bd=3, relief="raised", cursor="hand2", padx=6,
            command=lambda: self.open_calendar_picker("NSE")
        )
        cal_btn_nse.pack(side="left", padx=(5, 0))
        
        yesterday_btn_nse = tk.Button(
            date_container_nse, text="Yesterday", font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, 
            activeforeground=self.btn_active_fg, bd=3, relief="raised", cursor="hand2", padx=8, pady=2,
            command=lambda: self.set_date_to_yesterday("NSE")
        )
        yesterday_btn_nse.pack(side="left", padx=(5, 0))
        
        today_btn_nse = tk.Button(
            date_container_nse, text="Today", font=("Segoe UI", 8, "bold"),
            bg=self.primary_teal, fg=self.accent_btn_fg, activebackground=self.primary_purple, 
            activeforeground=self.accent_btn_fg, bd=3, relief="raised", cursor="hand2", padx=10, pady=2,
            command=lambda: self.set_date_to_today("NSE")
        )
        today_btn_nse.pack(side="left", padx=(5, 0))
 
        # Save Directory Path field (NSE Base Path)
        tk.Label(config_card_nse, text="NSE File Server Base Directory:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        path_container_nse = tk.Frame(config_card_nse, bg=self.card_color)
        path_container_nse.pack(fill="x", pady=(3, 8))
        
        self.path_ent_nse = self.create_styled_entry(path_container_nse)
        self.path_ent_nse.frame.pack(side="left", fill="x", expand=True)
        
        browse_btn_nse = tk.Button(
            path_container_nse, text="Browse...", font=("Segoe UI", 8, "bold"),
            bg=self.neon_yellow, fg="#000000", activebackground=self.primary_teal, 
            activeforeground="#000000", bd=3, relief="raised", cursor="hand2", padx=8, pady=2,
            command=lambda: self.browse_directory("NSE")
        )
        browse_btn_nse.pack(side="right", padx=(6, 0))
 
        # Save Settings Quick Button (NSE)
        save_settings_btn_nse = tk.Button(
            config_card_nse,
            text="💾  Save NSE Configuration",
            font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, activeforeground=self.btn_active_fg,
            bd=3, relief="raised", cursor="hand2", pady=5,
            command=lambda: self.save_settings_action("NSE")
        )
        save_settings_btn_nse.pack(fill="x")
        self.run_btn = tk.Button(
            self.pages_container, 
            text="🚀  START DOWNLOAD & RUN EXTRACTOR", 
            font=("Segoe UI", 11, "bold"), 
            bg=self.primary_teal, 
            fg="#000000", 
            activebackground=self.primary_teal, 
            activeforeground="#000000", 
            bd=4, 
            relief="raised", 
            cursor="hand2", 
            pady=10,
            command=self.start_download_process
        )
        self.run_btn.pack(fill="x", pady=(5, 10))
 
        # Central Shared Log Panel - Ridge Bezel
        log_panel = tk.Frame(
            self.pages_container, 
            bg=self.card_color, 
            bd=3, 
            relief="ridge", 
            padx=15, 
            pady=10
        )
        log_panel.pack(fill="both", expand=True)
        
        log_header = tk.Frame(log_panel, bg=self.card_color)
        log_header.pack(fill="x", pady=(0, 5))
        
        console_title = tk.Label(log_header, text="Console Log Output", font=("Segoe UI", 9, "bold"), fg=self.primary_teal, bg=self.card_color)
        console_title.pack(side="left")
        
        self.status_tag = tk.Label(
            log_header, 
            text="● IDLE", 
            font=("Segoe UI", 9, "bold"), 
            bg="#7f8c8d", 
            fg="#ffffff", 
            bd=2, 
            relief="sunken", 
            padx=15, 
            pady=2
        )
        self.status_tag.pack(side="right")
        
        # Terminal display box - Sunken Monitor Glass
        terminal_container = tk.Frame(
            log_panel, 
            bg=self.terminal_bg,
            bd=3,
            relief="sunken"
        )
        terminal_container.pack(fill="both", expand=True)
        
        self.log_widget = tk.Text(
            terminal_container, bg=self.terminal_bg, fg=self.terminal_fg, 
            insertbackground=self.terminal_fg, selectbackground="#2c3e50",
            font=("Consolas", 10), bd=0, padx=10, pady=8, state="disabled", wrap="word"
        )
        self.log_widget.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(terminal_container, orient="vertical", command=self.log_widget.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_widget.configure(yscrollcommand=scrollbar.set)
 
        # ── SLIDING CREDENTIALS DRAWER OVERLAY ──
        self.drawer_frame = tk.Frame(
            self.root, 
            bg=self.card_color, 
            highlightthickness=3, 
            highlightbackground="#000000", 
            bd=0
        )
        # Hidden outside the right edge initially
        self.drawer_frame.place(x=900, y=0, width=340, relheight=1.0)
        
        drawer_header = tk.Frame(self.drawer_frame, bg=self.card_color, pady=12, padx=20)
        drawer_header.pack(fill="x")
        
        tk.Label(
            drawer_header, 
            text="🔑  Extranet Login Settings", 
            font=("Segoe UI", 11, "bold"), 
            fg=self.primary_purple, 
            bg=self.card_color
        ).pack(side="left")
        
        close_drawer_btn = tk.Button(
            drawer_header, text="✕", font=("Segoe UI", 11, "bold"),
            bg=self.error_red, fg="#ffffff", activebackground=self.error_red,
            activeforeground="#ffffff", bd=3, relief="raised", cursor="hand2",
            padx=8, pady=2,
            command=self.toggle_drawer
        )
        close_drawer_btn.pack(side="right")
        
        drawer_body = tk.Frame(self.drawer_frame, bg=self.card_color, padx=20)
        drawer_body.pack(fill="both", expand=True)
        
        # Save credentials button in drawer
        save_cred_btn = tk.Button(
            drawer_body,
            text="💾  Save All Credentials & Close",
            font=("Segoe UI", 9, "bold"),
            bg=self.primary_purple, fg=self.accent_btn_fg, activebackground=self.primary_purple, activeforeground=self.accent_btn_fg,
            bd=3, relief="raised", cursor="hand2", pady=8,
            command=self.save_credentials_drawer_action
        )
        save_cred_btn.pack(fill="x", pady=(5, 12))
        
        # Section A: BSE Credentials
        bse_lbl = tk.Label(drawer_body, text="BSE EXTRANET LOGIN", font=("Segoe UI", 10, "bold"), fg=self.primary_teal, bg=self.card_color)
        bse_lbl.pack(anchor="w", pady=(5, 5))
        
        tk.Label(drawer_body, text="BSE Member ID:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        self.member_ent = self.create_styled_entry(drawer_body)
        self.member_ent.frame.pack(fill="x", pady=(2, 6))
        
        tk.Label(drawer_body, text="BSE User ID (Login ID):", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        self.bse_userid_ent = self.create_styled_entry(drawer_body)
        self.bse_userid_ent.frame.pack(fill="x", pady=(2, 6))
        
        tk.Label(drawer_body, text="BSE Password:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        pwd_container_bse = tk.Frame(drawer_body, bg=self.card_color)
        pwd_container_bse.pack(fill="x", pady=(2, 8))
        self.password_ent = self.create_styled_entry(pwd_container_bse, show="*")
        self.password_ent.frame.pack(side="left", fill="x", expand=True)
        
        self.pwd_visible_bse = False
        self.toggle_pwd_btn_bse = tk.Button(
            pwd_container_bse, text="👁", font=("Segoe UI", 9, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, 
            activeforeground=self.btn_active_fg, bd=3, relief="raised", cursor="hand2", padx=6,
            command=lambda: self.toggle_password_visibility("BSE")
        )
        self.toggle_pwd_btn_bse.pack(side="right", padx=(4, 0))
        
        # Separator line
        tk.Frame(drawer_body, height=2, bg="#000000").pack(fill="x", pady=8)
        
        # Section B: NSE API Credentials
        nse_lbl = tk.Label(drawer_body, text="NSE CONNECT API LOGIN", font=("Segoe UI", 10, "bold"), fg=self.primary_purple, bg=self.card_color)
        nse_lbl.pack(anchor="w", pady=(0, 5))
        
        tk.Label(drawer_body, text="NSE Member Code:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        self.nse_member_ent = self.create_styled_entry(drawer_body)
        self.nse_member_ent.frame.pack(fill="x", pady=(2, 6))
        
        tk.Label(drawer_body, text="NSE Login ID / User ID:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        self.nse_userid_ent = self.create_styled_entry(drawer_body)
        self.nse_userid_ent.frame.pack(fill="x", pady=(2, 6))
        
        tk.Label(drawer_body, text="NSE Password:", font=("Segoe UI", 9, "bold"), fg=self.text_color, bg=self.card_color).pack(anchor="w")
        pwd_container_nse = tk.Frame(drawer_body, bg=self.card_color)
        pwd_container_nse.pack(fill="x", pady=(2, 10))
        self.nse_password_ent = self.create_styled_entry(pwd_container_nse, show="*")
        self.nse_password_ent.frame.pack(side="left", fill="x", expand=True)
        
        self.pwd_visible_nse = False
        self.toggle_pwd_btn_nse = tk.Button(
            pwd_container_nse, text="👁", font=("Segoe UI", 9, "bold"),
            bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, 
            activeforeground=self.btn_active_fg, bd=3, relief="raised", cursor="hand2", padx=6,
            command=lambda: self.toggle_password_visibility("NSE")
        )
        self.toggle_pwd_btn_nse.pack(side="right", padx=(4, 0))

        # Prepopulate existing entries
        self.prepopulate_fields()

    def create_styled_entry(self, parent, show=None):
        frame = tk.Frame(parent, bg="#ffffff", bd=2, relief="sunken")
        
        ent = tk.Entry(
            frame, 
            bg="#ffffff", 
            fg="#000000", 
            insertbackground="#000000",
            bd=0, 
            font=("Segoe UI", 10), 
            show=show,
            relief="flat"
        )
        ent.pack(fill="both", expand=True, padx=6, pady=4)
        
        # Hover/focus border effects
        def on_enter(e):
            pass
        def on_leave(e):
            pass
        def on_focus_in(e):
            pass
        def on_focus_out(e):
            pass
            
        ent.bind("<Enter>", on_enter)
        ent.bind("<Leave>", on_leave)
        ent.bind("<FocusIn>", on_focus_in)
        ent.bind("<FocusOut>", on_focus_out)
        
        ent.frame = frame
        return ent

    def toggle_mode_btn(self, btn):
        if btn["text"] == "Custom Config":
            btn.config(text="All Files", bg=self.primary_teal, fg="#000000")
        else:
            btn.config(text="Custom Config", bg=self.btn_bg, fg=self.btn_fg)

    def switch_page(self, page_name):
        self.current_page = page_name
        if page_name == "BSE":
            self.nse_page.pack_forget()
            self.bse_page.pack(fill="both", expand=True)
            self.tab_bse_btn.config(bg=self.primary_teal, fg="#000000", bd=3, relief="raised")
            self.tab_nse_btn.config(bg=self.btn_bg, fg=self.text_color, bd=3, relief="sunken")
            self.run_btn.config(
                text="🚀  START BSE DOWNLOAD & RUN EXTRACTOR", 
                bg="#27ae60" if self.theme_mode == "light" else "#2ecc71",
                fg="#ffffff" if self.theme_mode == "light" else "#000000",
                activebackground=self.primary_teal,
                activeforeground="#000000",
                bd=4,
                relief="raised"
            )
        else:
            self.bse_page.pack_forget()
            self.nse_page.pack(fill="both", expand=True)
            self.tab_nse_btn.config(bg=self.primary_purple, fg="#000000", bd=3, relief="raised")
            self.tab_bse_btn.config(bg=self.btn_bg, fg=self.text_color, bd=3, relief="sunken")
            self.run_btn.config(
                text="🚀  START NSE DOWNLOAD & RUN API SUITE", 
                bg="#27ae60" if self.theme_mode == "light" else "#2ecc71",
                fg="#ffffff" if self.theme_mode == "light" else "#000000",
                activebackground=self.primary_purple,
                activeforeground="#000000",
                bd=4,
                relief="raised"
            )

    def toggle_theme(self):
        # Toggle theme state
        if self.theme_mode == "dark":
            self.theme_mode = "light"
        else:
            self.theme_mode = "dark"
            
        # Apply the new theme colors dynamically
        self.apply_theme()
        
        # Save theme setting to config.json
        if "config" not in self.config:
            self.config["config"] = {}
        self.config["config"]["theme"] = self.theme_mode
        try:
            save_config(self.config)
        except Exception:
            pass

    def apply_theme(self):
        # Update styling attributes based on self.theme_mode
        if self.theme_mode == "dark":
            self.bg_color = "#1e272e"
            self.card_color = "#2f3640"
            self.text_color = "#f5f6fa"
            self.text_dim = "#b2bec3"
            self.terminal_bg = "#0c0d10"
            self.terminal_fg = "#00ff66"
            self.btn_bg = "#353b48"
            self.btn_fg = "#f5f6fa"
            self.btn_active_bg = "#718093"
            self.btn_active_fg = "#ffffff"
            self.primary_teal = "#00a8ff"
            self.primary_purple = "#9c88ff"
            self.accent_btn_fg = "#000000"
        else:
            self.bg_color = "#dcdde1"
            self.card_color = "#f5f6fa"
            self.text_color = "#2f3640"
            self.text_dim = "#718093"
            self.terminal_bg = "#15171c"
            self.terminal_fg = "#ffb000"
            self.btn_bg = "#e2e8f0"
            self.btn_fg = "#2f3640"
            self.btn_active_bg = "#cbd5e1"
            self.btn_active_fg = "#000000"
            self.primary_teal = "#0066cc"
            self.primary_purple = "#7b2cbf"
            self.accent_btn_fg = "#ffffff"
            
        # Update root background
        self.root.configure(bg=self.bg_color)
        
        # Update TTK Styles
        if self.theme_mode == "dark":
            self.style.configure(
                "TScrollbar",
                gripcount=0,
                background="#ffffff",
                troughcolor=self.terminal_bg,
                bordercolor="#000000",
                arrowcolor="#000000",
                lightcolor="#ffffff",
                darkcolor="#ffffff"
            )
        else:
            self.style.configure(
                "TScrollbar",
                gripcount=0,
                background="#000000",
                troughcolor="#e5e7eb",
                bordercolor="#000000",
                arrowcolor="#ffffff",
                lightcolor="#000000",
                darkcolor="#000000"
            )
            
        # Update all widgets recursively
        self.update_widget_colors(self.root)
        
        # Explicitly fix tab button colors based on which tab is active
        self.switch_page(self.current_page)
        
        # Update theme button text/appearance
        if hasattr(self, "theme_btn"):
            self.theme_btn.config(
                text="☀  Light Mode" if self.theme_mode == "dark" else "🌙  Dark Mode"
            )

    def update_widget_colors(self, widget):
        try:
            w_class = widget.winfo_class()
        except Exception:
            return
        
        # 1. Handle Frame
        if w_class == "Frame":
            try:
                bg = widget.cget("bg")
                try:
                    relief = widget.cget("relief")
                except Exception:
                    relief = "flat"
                if relief == "sunken":
                    # Keep input slots white/disabled
                    pass
                else:
                    if bg in ["#121212", "#f3f4f6", "#1e272e", "#dcdde1"]:
                        widget.configure(bg=self.bg_color)
                    elif bg in ["#1e1e1e", "#ffffff", "#2f3640", "#f5f6fa"]:
                        widget.configure(bg=self.card_color)
            except Exception:
                pass
                    
        # 2. Handle Label
        elif w_class == "Label":
            try:
                bg = widget.cget("bg")
                fg = widget.cget("fg")
                
                # Update background color
                if bg in ["#121212", "#f3f4f6", "#1e272e", "#dcdde1"]:
                    widget.configure(bg=self.bg_color)
                elif bg in ["#1e1e1e", "#ffffff", "#2f3640", "#f5f6fa"]:
                    widget.configure(bg=self.card_color)
                    
                # Update text color
                if fg in ["#ffffff", "#000000", "#f5f6fa", "#2f3640"]:
                    if widget == self.status_tag:
                        if "IDLE" not in widget.cget("text"):
                            pass
                        else:
                            widget.configure(bg="#7f8c8d", fg="#ffffff")
                    else:
                        widget.configure(fg=self.text_color)
                elif fg in ["#aaaaaa", "#555555", "#b2bec3", "#718093"]:
                    widget.configure(fg=self.text_dim)
                elif fg in ["#00a8ff", "#0066cc"]:
                    widget.configure(fg=self.primary_teal)
                elif fg in ["#9c88ff", "#7b2cbf"]:
                    widget.configure(fg=self.primary_purple)
            except Exception:
                pass
                
        # 3. Handle Button
        elif w_class == "Button":
            try:
                bg = widget.cget("bg")
                fg = widget.cget("fg")
                
                if widget in [self.tab_bse_btn, self.tab_nse_btn]:
                    pass
                elif widget == self.run_btn:
                    widget.configure(bd=4)
                else:
                    text = widget.cget("text")
                    if text in ["Yesterday", "Today", "Browse...", "Save BSE Configuration", "Save NSE Configuration", "💾  Save All Credentials & Close", "👁", "✕ Close Settings", "☰ Credentials Menu", "✕"]:
                        widget.configure(bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, activeforeground=self.btn_active_fg, bd=3, relief="raised")
                    elif text == "Custom Config":
                        widget.configure(bg=self.btn_bg, fg=self.btn_fg, bd=3, relief="raised")
                    elif text == "All Files":
                        widget.configure(bg=self.primary_teal, fg=self.accent_btn_fg, bd=3, relief="raised")
                    elif bg in ["#121212", "#f3f4f6", "#1e272e", "#dcdde1", "#1e1e1e", "#ffffff", "#2f3640", "#f5f6fa"]:
                        widget.configure(bg=self.btn_bg, fg=self.btn_fg, bd=3, relief="raised")
            except Exception:
                pass
                    
        # 4. Handle Checkbutton
        elif w_class == "Checkbutton":
            try:
                bg = widget.cget("bg")
                if bg in ["#1e1e1e", "#ffffff", "#121212", "#f3f4f6", "#2f3640", "#f5f6fa", "#dcdde1", "#1e272e"]:
                    widget.configure(
                        bg=self.card_color, 
                        fg=self.text_color,
                        activebackground=self.card_color,
                        activeforeground=self.text_color,
                        selectcolor="#2f3640" if self.theme_mode == "dark" else "#ffffff"
                    )
            except Exception:
                pass
            
        # 5. Handle Text (terminal log)
        elif w_class == "Text":
            try:
                if widget == self.log_widget:
                    widget.configure(
                        bg=self.terminal_bg,
                        fg=self.terminal_fg,
                        insertbackground=self.terminal_fg
                    )
            except Exception:
                pass
                
        # Recurse for all children
        for child in widget.winfo_children():
            self.update_widget_colors(child)

    def toggle_drawer(self):
        if self.drawer_open:
            self.animate_drawer_close()
        else:
            self.drawer_frame.lift()
            self.animate_drawer_open()

    def animate_drawer_open(self):
        curr_x = self.drawer_frame.winfo_x()
        target_x = self.root.winfo_width() - 340
        if curr_x > target_x:
            new_x = max(target_x, curr_x - 30)
            self.drawer_frame.place(x=new_x, y=0, width=340, relheight=1.0)
            self.root.after(10, self.animate_drawer_open)
        else:
            self.drawer_open = True
            self.hamburger_btn.config(
                text="✕ Close Settings", 
                bg=self.error_red, 
                fg="#ffffff",
                activebackground=self.error_red, 
                activeforeground="#ffffff",
                relief="sunken"
            )

    def animate_drawer_close(self):
        curr_x = self.drawer_frame.winfo_x()
        target_x = self.root.winfo_width()
        if curr_x < target_x:
            new_x = min(target_x, curr_x + 30)
            self.drawer_frame.place(x=new_x, y=0, width=340, relheight=1.0)
            self.root.after(10, self.animate_drawer_close)
        else:
            self.drawer_open = False
            self.drawer_frame.place_forget()
            self.hamburger_btn.config(
                text="☰ Credentials Menu", 
                bg=self.btn_bg, 
                fg=self.btn_fg,
                activebackground=self.btn_active_bg, 
                activeforeground=self.btn_active_fg,
                relief="raised"
            )

    def toggle_password_visibility(self, exchange):
        if exchange == "BSE":
            if self.pwd_visible_bse:
                self.password_ent.config(show="*")
                self.toggle_pwd_btn_bse.config(text="👁", bg=self.btn_bg, fg=self.btn_fg, relief="raised")
                self.pwd_visible_bse = False
            else:
                self.password_ent.config(show="")
                self.toggle_pwd_btn_bse.config(text="🙈", bg=self.primary_teal, fg=self.accent_btn_fg, relief="sunken")
                self.pwd_visible_bse = True
        else:
            if self.pwd_visible_nse:
                self.nse_password_ent.config(show="*")
                self.toggle_pwd_btn_nse.config(text="👁", bg=self.btn_bg, fg=self.btn_fg, relief="raised")
                self.pwd_visible_nse = False
            else:
                self.nse_password_ent.config(show="")
                self.toggle_pwd_btn_nse.config(text="🙈", bg=self.primary_teal, fg=self.accent_btn_fg, relief="sunken")
                self.pwd_visible_nse = True

    def prepopulate_fields(self):
        # Load Extraction Modes
        modes = self.config.get("config", {}).get("Extraction_Modes", {})
        
        def set_mode(btn, key):
            val = modes.get(key, "Custom")
            if val == "All":
                btn.config(text="All Files", bg=self.primary_teal, fg="#000000")
            else:
                btn.config(text="Custom Config", bg=self.btn_bg, fg=self.btn_fg)
            
        set_mode(self.btn_cm_mode, "CM")
        set_mode(self.btn_fo_mode, "FO")
        set_mode(self.btn_cd_mode, "CDS")
        set_mode(self.btn_slb_mode, "SLB")
        self.update_combos_state()

        # 1. Credentials entries
        bse_ext = self.config.get("config", {}).get("BSE_WEBEXTRANET", {})
        self.member_ent.insert(0, bse_ext.get("Member_ID", ""))
        self.bse_userid_ent.insert(0, bse_ext.get("User_ID", ""))
        self.password_ent.insert(0, bse_ext.get("User_Password", ""))
        
        nse_api = self.config.get("config", {}).get("API_DETAILS", {}).get("NSE_API", {})
        self.nse_member_ent.insert(0, nse_api.get("MemberCode", ""))
        self.nse_userid_ent.insert(0, nse_api.get("LoginID", ""))
        self.nse_password_ent.insert(0, nse_api.get("Password", ""))
        
        # 2. BSE Folders selection
        main_folder_val = bse_ext.get("MainFolder", "EQ")
        sub_folder_val = bse_ext.get("SubFolder", "Transaction")
        self.main_folder_combo.set(main_folder_val)
        self.sub_folder_combo.set(sub_folder_val)
        
        # 3. Dates
        date_raw = self.config.get("config", {}).get("Dates", {}).get("Capital_Dates", {}).get("FromDate", "")
        if len(date_raw) == 8:
            formatted = f"{date_raw[:2]}-{date_raw[2:4]}-{date_raw[4:]}"
            self.date_ent_bse.insert(0, formatted)
            self.date_ent_nse.insert(0, formatted)
        else:
            today_str = datetime.today().strftime("%d-%m-%Y")
            self.date_ent_bse.insert(0, today_str)
            self.date_ent_nse.insert(0, today_str)
            
        # 4. Save Paths
        save_path_bse = self.config.get("config", {}).get("Path", {}).get("Equity", {}).get("BSECM", "")
        if not save_path_bse:
            save_path_bse = str(SCRIPT_DIR / "downloads")
        self.path_ent_bse.insert(0, save_path_bse)
        
        save_path_nse = self.config.get("config", {}).get("Path", {}).get("Equity", {}).get("NSECM", "")
        # Resolve Base Path from NSECM (strip cash folder)
        if save_path_nse:
            base_nse = save_path_nse.replace("CASH\\", "").replace("CASH", "")
        else:
            base_nse = "C:\\FILE\\"
        self.path_ent_nse.insert(0, base_nse)

    def set_date_to_today(self, exchange):
        today_str = datetime.today().strftime("%d-%m-%Y")
        if exchange == "BSE":
            self.date_ent_bse.delete(0, "end")
            self.date_ent_bse.insert(0, today_str)
        else:
            self.date_ent_nse.delete(0, "end")
            self.date_ent_nse.insert(0, today_str)

    def set_date_to_yesterday(self, exchange):
        yesterday_str = (datetime.today() - timedelta(days=1)).strftime("%d-%m-%Y")
        if exchange == "BSE":
            self.date_ent_bse.delete(0, "end")
            self.date_ent_bse.insert(0, yesterday_str)
        else:
            self.date_ent_nse.delete(0, "end")
            self.date_ent_nse.insert(0, yesterday_str)

    def open_calendar_picker(self, exchange):
        if exchange == "BSE":
            CalendarDialog(self.root, lambda d: self.on_date_selected("BSE", d), self.date_ent_bse.get().strip())
        else:
            CalendarDialog(self.root, lambda d: self.on_date_selected("NSE", d), self.date_ent_nse.get().strip())

    def on_date_selected(self, exchange, date_str):
        if exchange == "BSE":
            self.date_ent_bse.delete(0, "end")
            self.date_ent_bse.insert(0, date_str)
        else:
            self.date_ent_nse.delete(0, "end")
            self.date_ent_nse.insert(0, date_str)

    def browse_directory(self, exchange):
        ent = self.path_ent_bse if exchange == "BSE" else self.path_ent_nse
        curr = ent.get()
        if not curr or not os.path.exists(curr):
            curr = str(SCRIPT_DIR)
        selected = filedialog.askdirectory(initialdir=curr, title=f"Select {exchange} Download Directory")
        if selected:
            ent.delete(0, "end")
            ent.insert(0, selected.replace("/", "\\"))

    def validate_inputs(self, exchange="BSE"):
        # Validate Credentials
        if not self.member_ent.get().strip():
            messagebox.showerror("Validation Error", "BSE Member ID in Credentials Menu cannot be empty.")
            return False
        if not self.bse_userid_ent.get().strip():
            messagebox.showerror("Validation Error", "BSE User ID in Credentials Menu cannot be empty.")
            return False
        if not self.password_ent.get().strip():
            messagebox.showerror("Validation Error", "BSE Password in Credentials Menu cannot be empty.")
            return False
            
        if exchange == "NSE":
            if not self.nse_member_ent.get().strip():
                messagebox.showerror("Validation Error", "NSE Member Code in Credentials Menu cannot be empty.")
                return False
            if not self.nse_userid_ent.get().strip():
                messagebox.showerror("Validation Error", "NSE Login ID in Credentials Menu cannot be empty.")
                return False
            if not self.nse_password_ent.get().strip():
                messagebox.showerror("Validation Error", "NSE Password in Credentials Menu cannot be empty.")
                return False

        # Validate Date
        date_ent = self.date_ent_bse if exchange == "BSE" else self.date_ent_nse
        dt_str = date_ent.get().strip()
        try:
            datetime.strptime(dt_str, "%d-%m-%Y")
        except ValueError:
            messagebox.showerror("Validation Error", "Date must be in DD-MM-YYYY format (e.g. 25-05-2026).")
            return False
            
        # Validate Folders (BSE)
        if exchange == "BSE":
            if not self.main_folder_combo.get().strip():
                messagebox.showerror("Validation Error", "Main Category folder cannot be empty.")
                return False
            if not self.sub_folder_combo.get().strip():
                messagebox.showerror("Validation Error", "Target Subfolder cannot be empty.")
                return False

        # Validate Path
        path_ent = self.path_ent_bse if exchange == "BSE" else self.path_ent_nse
        path_str = path_ent.get().strip()
        if not path_str:
            messagebox.showerror("Validation Error", "Save path cannot be empty.")
            return False
            
        return True

    def save_settings_to_json(self, exchange="BSE"):
        if not self.validate_inputs(exchange):
            return False

        # Reload fresh config from disk to preserve manual edits (e.g. Master_Files)
        try:
            config_path = get_config_path()
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    disk_cfg = json.load(f)
                if "config" in disk_cfg and "Master_Files" in disk_cfg["config"]:
                    if "config" not in self.config:
                        self.config["config"] = {}
                    self.config["config"]["Master_Files"] = disk_cfg["config"]["Master_Files"]
        except Exception:
            pass

        # Standardize date to ddmmyyyy for script execution
        date_ent = self.date_ent_bse if exchange == "BSE" else self.date_ent_nse
        dt_str = date_ent.get().strip()
        dt_parsed = datetime.strptime(dt_str, "%d-%m-%Y")
        ddmmyyyy = dt_parsed.strftime("%d%m%Y")
        
        # Save Dates
        self.config["config"]["Dates"]["Capital_Dates"]["FromDate"] = ddmmyyyy
        
        # Save Extraction Modes
        if "Extraction_Modes" not in self.config["config"]:
            self.config["config"]["Extraction_Modes"] = {}
            
        def get_mode_val(btn):
            return "All" if btn["text"] == "All Files" else "Custom"
            
        self.config["config"]["Extraction_Modes"]["CM"] = get_mode_val(self.btn_cm_mode)
        self.config["config"]["Extraction_Modes"]["FO"] = get_mode_val(self.btn_fo_mode)
        self.config["config"]["Extraction_Modes"]["CDS"] = get_mode_val(self.btn_cd_mode)
        self.config["config"]["Extraction_Modes"]["SLB"] = get_mode_val(self.btn_slb_mode)
        
        # Save Credentials
        self.config["config"]["BSE_WEBEXTRANET"]["Member_ID"] = self.member_ent.get().strip()
        self.config["config"]["BSE_WEBEXTRANET"]["User_ID"] = self.bse_userid_ent.get().strip()
        self.config["config"]["BSE_WEBEXTRANET"]["User_Password"] = self.password_ent.get().strip()
        
        self.config["config"]["API_DETAILS"]["NSE_API"]["MemberCode"] = self.nse_member_ent.get().strip()
        self.config["config"]["API_DETAILS"]["NSE_API"]["LoginID"] = self.nse_userid_ent.get().strip()
        self.config["config"]["API_DETAILS"]["NSE_API"]["Password"] = self.nse_password_ent.get().strip()
        
        # Update Member Code node for older references
        if "Member_Code" not in self.config["config"]:
            self.config["config"]["Member_Code"] = {}
        self.config["config"]["Member_Code"]["BSE_CODE"] = self.member_ent.get().strip()
        self.config["config"]["Member_Code"]["BSE_CODE_2"] = self.member_ent.get().strip()
        self.config["config"]["Member_Code"]["NSE_CODE"] = self.nse_member_ent.get().strip()
        
        if exchange == "BSE":
            # Update Dynamic folder selections
            self.config["config"]["BSE_WEBEXTRANET"]["MainFolder"] = self.main_folder_combo.get().strip()
            self.config["config"]["BSE_WEBEXTRANET"]["SubFolder"] = self.sub_folder_combo.get().strip()
            
            # Update PC save paths in config (Equity: BSECM, BSE_CM_Common, BSE_CM_Transaction)
            target_path = self.path_ent_bse.get().strip().rstrip("\\").rstrip("/") + "\\"
            
            path_cfg = self.config["config"]["Path"]
            if "Equity" not in path_cfg:
                path_cfg["Equity"] = {}
            path_cfg["Equity"]["BSECM"] = target_path
            path_cfg["Equity"]["BSE_CM_Common"] = target_path
            path_cfg["Equity"]["BSE_CM_Transaction"] = target_path
        else:
            # Update NSE save paths (resolve base path)
            base_path = self.path_ent_nse.get().strip().rstrip("\\").rstrip("/") + "\\"
            
            path_cfg = self.config["config"]["Path"]
            if "Equity" not in path_cfg:
                path_cfg["Equity"] = {}
            if "FO" not in path_cfg:
                path_cfg["FO"] = {}
            if "CDS" not in path_cfg:
                path_cfg["CDS"] = {}
            if "SLB" not in path_cfg:
                path_cfg["SLB"] = {}
                
            path_cfg["Equity"]["NSECM"] = base_path + "CASH\\"
            path_cfg["FO"]["NSEFO"] = base_path + "NSEFO\\"
            path_cfg["CDS"]["NSECD"] = base_path + "NSECD\\"
            path_cfg["SLB"]["NSESLB"] = base_path + "NSESLB\\"
            
            # Automatically pre-create segment subfolders to prevent WinError 3 crashes
            for segment_dir in ["CASH", "NSEFO", "NSECD", "NSESLB"]:
                try:
                    os.makedirs(os.path.join(base_path, segment_dir), exist_ok=True)
                except Exception:
                    pass
            
        # Save theme setting
        if "config" not in self.config:
            self.config["config"] = {}
        self.config["config"]["theme"] = self.theme_mode

        # Save to file
        try:
            save_config(self.config)
            
            # Create local workpath.txt next to app pointing to SCRIPT_DIR
            # NSE scripts read workpath.txt to identify where config.json resides!
            workpath_file = SCRIPT_DIR / "workpath.txt"
            workpath_file.write_text(str(SCRIPT_DIR))
            
            # Ensure local logs directory exists next to application so NSE logging works
            logs_dir = SCRIPT_DIR / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            return True
        except Exception as e:
            messagebox.showerror("File Error", f"Could not write config.json: {e}")
            return False

    def save_settings_action(self, exchange):
        if self.save_settings_to_json(exchange):
            messagebox.showinfo("Success", f"{exchange} dynamic configuration saved successfully!")

    def save_credentials_drawer_action(self):
        # Validate and save BSE / NSE configs
        if self.save_settings_to_json(self.current_page):
            self.toggle_drawer()
            messagebox.showinfo("Success", "All exchange login credentials saved successfully!")

    def set_inputs_state(self, state):
        entry_widgets = [
            self.member_ent, self.bse_userid_ent, self.password_ent, 
            self.nse_member_ent, self.nse_userid_ent, self.nse_password_ent, 
            self.date_ent_bse, self.path_ent_bse,
            self.date_ent_nse, self.path_ent_nse
        ]
        for ent in entry_widgets:
            if state == "disabled":
                ent.config(state="disabled", disabledbackground="#e0e0e0", disabledforeground="#555555")
                ent.frame.config(bg="#e0e0e0", relief="sunken", bd=2)
            else:
                ent.config(state="normal", bg="#ffffff", fg="#000000")
                ent.frame.config(bg="#ffffff", relief="sunken", bd=2)
                
        # Also handle combo boxes state
        self.main_folder_combo.config(state=state)
        self.sub_folder_combo.config(state=state)
        if state == "disabled":
            self.btn_cm_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")
            self.btn_fo_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")
            self.btn_cd_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")
            self.btn_slb_mode.config(state="disabled", bg="#333333" if self.theme_mode == "dark" else "#cbd5e1", fg="#888888" if self.theme_mode == "dark" else "#9ca3af")
        else:
            self.update_combos_state()

    def append_log(self, text):
        self.log_widget.config(state="normal")
        self.log_widget.insert("end", text)
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    def poll_log_queue(self):
        while not log_queue.empty():
            try:
                msg = log_queue.get_nowait()
                self.append_log(msg)
            except queue.Empty:
                break
        self.root.after(50, self.poll_log_queue)

    def start_download_process(self):
        if self.running:
            return
            
        mode = self.current_page
        if not self.save_settings_to_json(mode):
            return
            
        # Set abort flag to False at the start of every run
        sys.abort_requested = False
            
        # Clear log console
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.config(state="disabled")
        
        # Close credentials drawer if open
        if self.drawer_open:
            self.toggle_drawer()
        
        self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] Launching {mode} Extranet Downloader Process...\n")
        self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] Settings verified and updated.\n\n")
        
        # Disable all controls during running
        self.set_inputs_state("disabled")
        self.running = True
        
        # Enable stop mode on the action button
        self.run_btn.config(
            text="🛑  STOP ACTIVE DOWNLOAD PROCESS",
            bg=self.error_red,
            fg=self.text_color,
            activebackground=self.error_red,
            activeforeground=self.text_color,
            command=self.stop_download_process
        )
        self.status_tag.config(
            text="RUNNING",
            bg=self.primary_teal if mode == "BSE" else self.primary_purple,
            fg=self.bg_color
        )
        
        # Redirect stdout and stderr globally
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = GUIConsoleWriter(log_queue)
        sys.stderr = GUIConsoleWriter(log_queue)
        
        # Start executing script in thread
        if mode == "BSE":
            th = threading.Thread(target=self.run_downloader_thread_bse, daemon=True)
        else:
            th = threading.Thread(target=self.run_downloader_thread_nse, daemon=True)
        th.start()

    def stop_download_process(self):
        sys.abort_requested = True
        self.append_log("\n[USER STOP] Abort signal sent! Stopping execution threads. Please wait...\n")
        self.status_tag.config(text="STOPPING", bg=self.error_red, fg=self.text_color)
        self.run_btn.config(state="disabled", bg="#1e292b", fg="#4b5563")

    def run_downloader_thread_bse(self):
        success = False
        try:
            # We import and dynamically reload the script to make sure it loads 
            # the newly written config.json values on every run.
            import bse_extranet_downloader
            importlib.reload(bse_extranet_downloader)
            
            # Execute downloader main
            bse_extranet_downloader.main()
            success = True
        except SystemExit as se:
            success = (se.code == 0 or se.code is None)
        except Exception as e:
            print(f"\n[GUI CRITICAL ERROR] Execution crashed with exception:\n{e}")
            success = False
        finally:
            self.root.after(0, self.on_download_complete, success)

    def run_downloader_thread_nse(self):
        success = True
        try:
            # 1. Determine selected segments
            segments = []
            if self.nse_cm_val.get(): segments.append("CM")
            if self.nse_fo_val.get(): segments.append("FO")
            if self.nse_cd_val.get(): segments.append("CD")
            if self.nse_slb_val.get(): segments.append("SLB")
            
            if not segments:
                print("[GUI ERROR] No NSE segments selected for download! Please check at least one segment.")
                success = False
            else:
                # 2. Run each selected module sequentially
                for seg in segments:
                    if seg == "CM":
                        print("\n" + "=" * 65)
                        print("  STARTING NSE CASH MARKET (CM) DOWNLOAD...")
                        print("=" * 65 + "\n")
                        import nse.NSE_CM_API_DOWNLOAD
                        importlib.reload(nse.NSE_CM_API_DOWNLOAD)
                        
                    elif seg == "FO":
                        print("\n" + "=" * 65)
                        print("  STARTING NSE FUTURES & OPTIONS (FO) DOWNLOAD...")
                        print("=" * 65 + "\n")
                        import nse.NSE_FO_API_DOWNLOAD
                        importlib.reload(nse.NSE_FO_API_DOWNLOAD)
                        
                    elif seg == "CD":
                        print("\n" + "=" * 65)
                        print("  STARTING NSE CURRENCY DERIVATIVES (CD) DOWNLOAD...")
                        print("=" * 65 + "\n")
                        import nse.NSE_CD_API_DOWNLOAD_AI
                        importlib.reload(nse.NSE_CD_API_DOWNLOAD_AI)
                        # The CD script uses main entrypoint process()
                        nse.NSE_CD_API_DOWNLOAD_AI.process()
                        
                    elif seg == "SLB":
                        print("\n" + "=" * 65)
                        print("  STARTING NSE SECURITIES LENDING & BORROWING (SLB) DOWNLOAD...")
                        print("=" * 65 + "\n")
                        import nse.NSE_SLB_API_DOWNLOAD
                        importlib.reload(nse.NSE_SLB_API_DOWNLOAD)
                        
        except SystemExit as se:
            success = (se.code == 0 or se.code is None)
        except Exception as e:
            print(f"\n[GUI CRITICAL ERROR] Execution crashed with exception:\n{e}")
            success = False
        finally:
            self.root.after(0, self.on_download_complete, success)

    def on_download_complete(self, success):
        # Restore normal output routing
        if self.old_stdout:
            sys.stdout = self.old_stdout
        if self.old_stderr:
            sys.stderr = self.old_stderr
            
        self.running = False
        self.set_inputs_state("normal")
        
        mode = self.current_page
        
        # Restore button to normal state
        if mode == "BSE":
            self.run_btn.config(
                state="normal",
                text="🚀  START BSE DOWNLOAD & RUN EXTRACTOR", 
                bg="#27ae60" if self.theme_mode == "light" else "#2ecc71",
                fg="#ffffff" if self.theme_mode == "light" else "#000000",
                activebackground=self.primary_teal,
                activeforeground="#000000",
                bd=4,
                relief="raised",
                command=self.start_download_process
            )
        else:
            self.run_btn.config(
                state="normal",
                text="🚀  START NSE DOWNLOAD & RUN API SUITE", 
                bg="#27ae60" if self.theme_mode == "light" else "#2ecc71",
                fg="#ffffff" if self.theme_mode == "light" else "#000000",
                activebackground=self.primary_purple,
                activeforeground="#000000",
                bd=4,
                relief="raised",
                command=self.start_download_process
            )
            
        if success:
            if getattr(sys, 'abort_requested', False):
                self.status_tag.config(text="ABORTED", bg=self.error_red, fg="#ffffff")
                self.append_log(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> {mode} DOWNLOAD RUN ABORTED BY USER! <<<\n")
                messagebox.showwarning("Status Update", f"{mode} Downloader run stopped by user!")
            else:
                self.status_tag.config(text="SUCCESS", bg=self.success_green, fg="#000000")
                self.append_log(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> {mode} DOWNLOAD RUN COMPLETED SUCCESSFULLY! <<<\n")
                messagebox.showinfo("Status Update", f"{mode} Extranet Downloader finished successfully!")
        else:
            self.status_tag.config(text="FAILED", bg=self.error_red, fg="#ffffff")
            self.append_log(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> {mode} DOWNLOAD RUN FAILED! Check logs above for details. <<<\n")
            messagebox.showerror("Status Update", f"{mode} Downloader run failed! Check terminal logs for details.")

    def show_contact_popup(self):
        # Create modal window
        popup = tk.Toplevel(self.root)
        popup.title("Contact Developer")
        popup.geometry("380x320")
        popup.resizable(False, False)
        popup.configure(bg=self.bg_color)
        
        # Set icon for popup
        try:
            icon_path = get_resource_path("TRANSPARENT LOGO.png")
            if not icon_path.exists():
                icon_path = get_resource_path("LOGO.png")
            if icon_path.exists():
                img = Image.open(icon_path)
                self.icon_photo_popup = ImageTk.PhotoImage(img)
                popup.iconphoto(True, self.icon_photo_popup)
        except Exception:
            pass
            
        # Transient over main window
        popup.transient(self.root)
        popup.grab_set()
        
        # Center the popup relative to root window
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()
        pos_x = root_x + (root_w - 380) // 2
        pos_y = root_y + (root_h - 320) // 2
        popup.geometry(f"+{pos_x}+{pos_y}")
        
        # Header Label
        tk.Label(
            popup,
            text="✉  Developer Information",
            font=("Segoe UI", 12, "bold"),
            fg=self.primary_purple,
            bg=self.bg_color
        ).pack(pady=(20, 15))
        
        # Main details container card - Bevel Border
        card = tk.Frame(
            popup, 
            bg=self.card_color, 
            bd=3, 
            relief="raised", 
            padx=15, 
            pady=15
        )
        card.pack(fill="both", expand=True, padx=25, pady=(0, 20))
        
        # Link helper function to add underline hover effect
        def create_link_row(parent, label, value, url, row_idx):
            tk.Label(
                parent,
                text=label,
                font=("Segoe UI", 9, "bold"),
                fg=self.text_color,
                bg=self.card_color
            ).grid(row=row_idx, column=0, sticky="w", pady=6)
            
            link_lbl = tk.Label(
                parent,
                text=value,
                font=("Segoe UI", 9, "underline", "bold"),
                fg=self.primary_teal,
                bg=self.card_color,
                cursor="hand2"
            )
            link_lbl.grid(row=row_idx, column=1, sticky="w", padx=(10, 0), pady=6)
            
            def open_link(e):
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                    
            def on_enter(e):
                link_lbl.config(fg=self.neon_yellow)
            def on_leave(e):
                link_lbl.config(fg=self.primary_teal)
                
            link_lbl.bind("<Button-1>", open_link)
            link_lbl.bind("<Enter>", on_enter)
            link_lbl.bind("<Leave>", on_leave)
            
        create_link_row(card, "Website:", "roshan-chaudhary.in", "https://roshan-chaudhary.in", 0)
        create_link_row(card, "LinkedIn:", "roshan-chaudhary", "https://www.linkedin.com/in/13-roshan-chaudhary/", 1)
        create_link_row(card, "Instagram:", "@roshan_13_03", "https://www.instagram.com/roshan_13_03/", 2)
        create_link_row(card, "Email:", "work@roshan-chaudhary.in", "mailto:work@roshan-chaudhary.in", 3)
        
        # Close Button - Bevel Border
        close_btn = tk.Button(
            popup,
            text="Close Window",
            font=("Segoe UI", 9, "bold"),
            bg=self.neon_yellow,
            fg="#000000",
            activebackground=self.primary_teal,
            activeforeground="#000000",
            bd=3,
            relief="raised",
            cursor="hand2",
            padx=20,
            pady=5,
            command=popup.destroy
        )
        close_btn.pack(pady=(0, 20))

# ── Main Entrypoint ────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    
    # Beautiful flat modern look on Windows
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
        
    app = BSEDownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()