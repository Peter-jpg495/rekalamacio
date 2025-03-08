#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Péternek: Reklamáció Kezelő Rendszer – Tkinter GUI + JSON alapú perzisztens tárolás

1. Mellékletek (képek/fájlok) törlése egyenként
2. Teljes reklamáció törlése (fotók törlése a mappából)
3. Elegánsabb, színesebb UI (alap ttk stílus)
4. Okos keresés: több mező egyidejű keresése, dátum és státusz szűrés
5. Exportálás különböző formátumokba (CSV, Excel-szerű, PDF-szerű)
6. Dashboard nézet a határidők és reklamációk áttekintéséhez
"""

import os
import json
import shutil
import datetime
import webbrowser
import subprocess  # Mac-en fájl megnyitáshoz
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv  # CSV exportáláshoz
import calendar  # Dashboard naptár nézethez
import re  # Reguláris kifejezésekhez
import io  # String IO műveletekhez

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

DATA_FILE = "/Users/ujvaripeter/complaints_data.json"

# Fotók/fájlok fix, abszolút elérési útvonala
PHOTOS_DIR = "/Users/ujvaripeter/Desktop/PythonProject/Reclamation/photos"

BRAND_OPTIONS = [
    "Novetex",
    "Tempur",
    "Hollandia",
    "Reflex",
    "Sealy",
    "Elitestrom"
]


class DataManager:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.complaints = {}
        self.load_complaints()

    def load_complaints(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.complaints = json.load(f)
            except:
                # Ha sérült a fájl vagy hiba van, legyen üres
                self.complaints = {}
        else:
            self.complaints = {}

    def save_complaints(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.complaints, f, ensure_ascii=False, indent=4)

    def ensure_photos_folder(self):
        if not os.path.exists(PHOTOS_DIR):
            os.makedirs(PHOTOS_DIR)
    
    def get_stats(self):
        """Statisztikákat gyűjt az összes reklamációról"""
        stats = {
            "total": len(self.complaints),
            "open": 0,
            "closed": 0,
            "overdue": 0,
            "pending_manufacturer": 0,
            "brands": {},
            "recent": []
        }
        
        today = datetime.date.today()
        
        for comp_no, comp_data in self.complaints.items():
            # Státusz számolás
            status = comp_data.get("status", "open")
            if status == "open":
                stats["open"] += 1
            else:
                stats["closed"] += 1
                
            # Márka statisztika
            brand = comp_data.get("brand", "Ismeretlen")
            if brand in stats["brands"]:
                stats["brands"][brand] += 1
            else:
                stats["brands"][brand] = 1
                
            # Határidő ellenőrzés
            start = comp_data.get("start_date")
            dl_days = comp_data.get("deadline_days")
            if start and dl_days and status == "open":
                try:
                    start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                    days_passed = (today - start_date).days
                    days_left = int(dl_days) - days_passed
                    if days_left < 0:
                        stats["overdue"] += 1
                except:
                    pass
            
            # Gyártói válasz függőben
            man_sent = comp_data.get("manufacturer_sent_date", None)
            man_resp = comp_data.get("manufacturer_response", "")
            if man_sent and not man_resp and status == "open":
                stats["pending_manufacturer"] += 1
                
            # Legutóbbi reklamációk (legfeljebb 5)
            if len(stats["recent"]) < 5:
                stats["recent"].append({
                    "comp_no": comp_no,
                    "customer": comp_data.get("customer", ""),
                    "status": status,
                    "brand": brand
                })
        
        return stats


class ComplaintApp(tk.Tk):
    def __init__(self, data_manager):
        super().__init__()
        self.title("Reklamációkezelő Rendszer")

        # Teljes ablak sötét háttere
        self.configure(bg="#2B2B2B")

        self.data_manager = data_manager
        self.geometry("1100x650")
        self.minsize(900, 550)  # Minimális ablakméret

        # UI stílus beállítása (ttk) – sötét téma
        self.configure_ui_style()
        
        # Dashboard megjelenítése alapértelmezetten
        self.show_dashboard = tk.BooleanVar(value=False)
        
        # Notebook panel a főablak és a dashboard között váltáshoz
        self.create_notebook()
        self.create_widgets()
        self.create_dashboard_panel()
        
        self.check_deadlines()
        self.refresh_tree()
        
        # Exportálási beállítások inicializálása
        self.setup_export_options()

    def setup_export_options(self):
        """Exportálási beállítások inicializálása"""
        self.export_formats = {
            "csv": {"ext": ".csv", "name": "CSV fájl", "func": self.export_to_csv},
            "html": {"ext": ".html", "name": "HTML táblázat", "func": self.export_to_html},
            "text": {"ext": ".txt", "name": "Szöveges fájl", "func": self.export_to_text}
        }

    def create_notebook(self):
        """Létrehozza a fő notebook komponenst a különböző nézetek között váltáshoz"""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Fő panel (reklamáció kezelő)
        self.main_panel = ttk.Frame(self.notebook)
        self.notebook.add(self.main_panel, text="Reklamációkezelő")
        
        # Dashboard panel
        self.dashboard_panel = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_panel, text="Dashboard")
        
        # Tab váltáskor frissítsük a dashboardot
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        """Tab váltásakor frissíti a megfelelő nézetet"""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:  # Dashboard tab
            self.refresh_dashboard()

    def configure_ui_style(self):
        """
        Elegánsabb, sötét kinézet a ttk elemeknek.
        """
        style = ttk.Style(self)
        style.theme_use('clam')

        # Alap (minden ttk elem) háttere és színe
        style.configure('.', background="#2B2B2B", foreground="white", font=('Arial', 10))

        # Treeview fejlécek sötét háttere
        style.configure('Treeview.Heading',
                        background="#2B2B2B",
                        foreground="white",
                        font=('Arial', 10, 'bold'),
                        relief="flat")
        
        # Treeview sorok - kiemelt sormagasság
        style.configure('Treeview',
                        background="#2B2B2B",
                        fieldbackground="#2B2B2B",
                        foreground="white",
                        rowheight=25,  # Magasabb sormagasság
                        borderwidth=0)
        
        # Kijelölt sorok színe
        style.map('Treeview',
                  background=[('selected', '#306998')],
                  foreground=[('selected', 'white')])

        # Gombstílus (TButton) - elegánsabb, lekerekített
        style.configure('TButton',
                        font=('Arial', 10, 'bold'),
                        foreground="#4B8BBE",
                        background="#2B2B2B",
                        borderwidth=1,
                        focusthickness=3,
                        focuscolor='#306998',
                        padding=(10, 5))  # Vízszintes és függőleges padding
        
        style.map('TButton',
                  foreground=[('active', '#FFFFFF')],
                  background=[('active', '#306998')])

        # Címkék stílusa
        style.configure('TLabel',
                        background="#2B2B2B",
                        foreground="white",
                        font=('Arial', 10))
        
        # Címkék (félkövér) stílusa
        style.configure('Bold.TLabel',
                        background="#2B2B2B",
                        foreground="white",
                        font=('Arial', 10, 'bold'))
        
        # Fejléc címke stílus
        style.configure('Header.TLabel',
                        background="#2B2B2B",
                        foreground="white",
                        font=('Arial', 12, 'bold'))

        # Notebook stílus (Dashboard és főnézet)
        style.configure('TNotebook',
                       background="#2B2B2B",
                       foreground="white",
                       tabmargins=[5, 5, 0, 0])
        
        style.configure('TNotebook.Tab',
                      background="#2B2B2B",
                      foreground="white",
                      padding=[10, 2],
                      font=('Arial', 10))
        
        style.map('TNotebook.Tab',
                 foreground=[('selected', 'white')],
                 background=[('selected', '#306998')])

        # --- Combobox stílus sötét témához ---
        style.configure('TCombobox',
                        foreground='white',
                        background='#2B2B2B',
                        fieldbackground='#4B4B4B',
                        arrowcolor='white',
                        padding=5)

        # Állapot szerinti színmapping
        style.map('TCombobox',
                  fieldbackground=[('readonly', '#2B2B2B'),
                                   ('!disabled', '#4B4B4B')],
                  selectbackground=[('focus', '#306998')],
                  selectforeground=[('focus', 'white')])
        
        # Frame stílus - szegéllyel
        style.configure('Card.TFrame',
                        background="#2B2B2B",
                        borderwidth=1,
                        relief="solid")
        
        # LabelFrame stílus 
        style.configure('TLabelframe', 
                        background="#2B2B2B",
                        foreground="white",
                        borderwidth=1,
                        relief="solid")
        
        style.configure('TLabelframe.Label', 
                        background="#2B2B2B",
                        foreground="white",
                        font=('Arial', 10, 'bold'))
        
        # Scrollbar stílus
        style.configure('TScrollbar',
                        background="#2B2B2B",
                        troughcolor="#4B4B4B",
                        borderwidth=0,
                        arrowsize=13)
                        
        # Checkbox stílus
        style.configure('TCheckbutton',
                        background="#2B2B2B",
                        foreground="white")
        
        style.map('TCheckbutton',
                 background=[('active', '#2B2B2B')],
                 foreground=[('active', 'white')])
                 
        # Dashboard panel stílus
        style.configure('Dashboard.TFrame',
                        background="#2B2B2B",
                        padding=10)
                        
        # Stat panel stílusok
        style.configure('Stat.TFrame',
                        background="#1E1E1E",
                        relief="solid",
                        borderwidth=1)
                        
        # Calendar Day stílus
        style.configure('CalDay.TLabel',
                        background="#2B2B2B",
                        foreground="white",
                        font=('Arial', 9),
                        padding=2,
                        anchor="center")
                        
        # Calendar Day Today stílus
        style.configure('CalToday.TLabel',
                        background="#306998",
                        foreground="white",
                        font=('Arial', 9, 'bold'),
                        padding=2,
                        anchor="center")
                        
        # Calendar Day With Event stílus
        style.configure('CalEvent.TLabel',
                        background="#4B8BBE",
                        foreground="white",
                        font=('Arial', 9),
                        padding=2,
                        anchor="center")
                        
        # Calendar Header stílus
        style.configure('CalHeader.TLabel',
                        background="#2B2B2B",
                        foreground="#4B8BBE",
                        font=('Arial', 10, 'bold'),
                        padding=2,
                        anchor="center")

    # ----------------------------------------------------------------
    #                        FŐ GUI ELEMEK
    # ----------------------------------------------------------------
    def create_widgets(self):
        """Létrehozza a fő GUI elemeket"""
        # Fő menüsor keretben, szebb térközökkel
        menu_frame = ttk.Frame(self.main_panel, style='Card.TFrame', padding=10)
        menu_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        # Keresés és címkék egységes elrendezéssel
        search_frame = ttk.Frame(menu_frame, padding=5)
        search_frame.pack(side=tk.TOP, fill=tk.X, expand=False)
        
        ttk.Label(search_frame, text="Gyorskeresés:", style='Bold.TLabel').pack(side=tk.LEFT, padx=5)
        self.search_entry = tk.Entry(search_frame, width=30, bg="#4B4B4B", fg="white", insertbackground="white", 
                               font=('Arial', 10), relief="flat", bd=5)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(search_frame, text="Keresés", command=self.search_complaints).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Részletes keresés", command=self.open_advanced_search).pack(side=tk.LEFT, padx=5)
        
        # Gombok jobb elrendezéssel
        buttons_frame = ttk.Frame(menu_frame, padding=5)
        buttons_frame.pack(side=tk.TOP, fill=tk.X, expand=False, pady=5)
        
        # Első sor gombok
        ttk.Button(buttons_frame, text="Új Reklamáció", command=self.add_complaint_window).pack(side=tk.LEFT, padx=3, pady=2)
        ttk.Button(buttons_frame, text="Részletek / Módosítás", command=self.view_details_window).pack(side=tk.LEFT, padx=3, pady=2)
        ttk.Button(buttons_frame, text="Fájl csatolása", command=self.add_media).pack(side=tk.LEFT, padx=3, pady=2)
        ttk.Button(buttons_frame, text="Lezárás", command=self.close_complaint).pack(side=tk.LEFT, padx=3, pady=2)
        ttk.Button(buttons_frame, text="Reklamáció törlése", command=self.delete_complaint).pack(side=tk.LEFT, padx=3, pady=2)
        
        # Második sor - Export és beadvány gombok
        buttons_frame2 = ttk.Frame(menu_frame, padding=5)
        buttons_frame2.pack(side=tk.TOP, fill=tk.X, expand=False)
        
        ttk.Button(buttons_frame2, text="Exportálás", command=self.show_export_options).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons_frame2, text="Beadvány (Szöveges)", command=self.generate_text_submission).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons_frame2, text="Beadvány (HTML)", command=self.generate_html_submission).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons_frame2, text="Dokumentáció generálása", command=self.generate_documentation).pack(side=tk.LEFT, padx=3)

        # TreeView keretben és scrollbar-ral
        tree_frame = ttk.Frame(self.main_panel, padding=10)
        tree_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        
        # TreeView beállítása
        columns = ("complaint_number", "customer", "product_name", "brand", "status", "deadline")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        # Fejlécek beállítása
        self.tree.heading("complaint_number", text="Rek. Szám")
        self.tree.heading("customer", text="Vásárló")
        self.tree.heading("product_name", text="Termék")
        self.tree.heading("brand", text="Márka")
        self.tree.heading("status", text="Státusz")
        self.tree.heading("deadline", text="Határidő")

        # Oszlopok szélességének finomítása
        self.tree.column("complaint_number", width=120, minwidth=100)
        self.tree.column("customer", width=200, minwidth=180)
        self.tree.column("product_name", width=240, minwidth=200)
        self.tree.column("brand", width=120, minwidth=100)
        self.tree.column("status", width=150, minwidth=120)
        self.tree.column("deadline", width=120, minwidth=100)

        # Scrollbar a TreeView-hoz
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # TreeView és scrollbar elrendezése
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Állapotsor (státusz)
        self.status_var = tk.StringVar(value="Betöltés sikeres. Készen áll.")
        status_frame = ttk.Frame(self)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                 anchor=tk.W, padding=(10, 5))
        status_label.pack(side=tk.LEFT, fill=tk.X)

    # ----------------------------------------------------------------
    #                 DASHBOARD / ÁTTEKINTŐ NÉZET
    # ----------------------------------------------------------------
    def create_dashboard_panel(self):
        """Dashboard panel létrehozása"""
        # Főkeret a dashboardnak
        dashboard_main = ttk.Frame(self.dashboard_panel, style='Dashboard.TFrame')
        dashboard_main.pack(fill=tk.BOTH, expand=True)
        
        # Fejléc
        header_frame = ttk.Frame(dashboard_main)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        header = ttk.Label(header_frame, text="Reklamáció Áttekintés", style='Header.TLabel',
                          font=('Arial', 14, 'bold'))
        header.pack(side=tk.LEFT)
        
        refresh_btn = ttk.Button(header_frame, text="Frissítés", 
                                command=self.refresh_dashboard, width=10)
        refresh_btn.pack(side=tk.RIGHT)
        
        # Felső sor - statisztikai panelek
        stats_frame = ttk.Frame(dashboard_main)
        stats_frame.pack(fill=tk.X, pady=5)
        
        # Statisztikai kártyák létrehozása
        self.stat_total = self.create_stat_panel(stats_frame, "Összes reklamáció", "0")
        self.stat_open = self.create_stat_panel(stats_frame, "Nyitott", "0")
        self.stat_closed = self.create_stat_panel(stats_frame, "Lezárt", "0")
        self.stat_overdue = self.create_stat_panel(stats_frame, "Határidőn túli", "0")
        self.stat_pending = self.create_stat_panel(stats_frame, "Gyártói válasz függőben", "0")
        
        # Középső sor - naptár és márka eloszlás
        middle_frame = ttk.Frame(dashboard_main)
        middle_frame.pack(fill=tk.X, pady=10, expand=True)
        
        # Bal oldali naptár panel
        calendar_frame = ttk.LabelFrame(middle_frame, text="Határidők naptára")
        calendar_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Naptár fejléc
        cal_header = ttk.Frame(calendar_frame)
        cal_header.pack(fill=tk.X, pady=5)
        
        self.month_var = tk.StringVar()
        
        prev_month_btn = ttk.Button(cal_header, text="←", width=3,
                                   command=lambda: self.change_month(-1))
        prev_month_btn.pack(side=tk.LEFT, padx=5)
        
        month_label = ttk.Label(cal_header, textvariable=self.month_var, style='Bold.TLabel')
        month_label.pack(side=tk.LEFT, expand=True)
        
        next_month_btn = ttk.Button(cal_header, text="→", width=3,
                                   command=lambda: self.change_month(1))
        next_month_btn.pack(side=tk.RIGHT, padx=5)
        
        # Naptár tartalom keret
        self.calendar_content = ttk.Frame(calendar_frame)
        self.calendar_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Jobb oldali márka eloszlás panel
        brands_frame = ttk.LabelFrame(middle_frame, text="Márka eloszlás")
        brands_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Márka statisztika keret
        self.brands_content = ttk.Frame(brands_frame)
        self.brands_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Alsó sor - Legutóbbi reklamációk
        bottom_frame = ttk.LabelFrame(dashboard_main, text="Legutóbbi reklamációk")
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Legutóbbi reklamációk tábla
        columns = ("comp_no", "customer", "brand", "status")
        self.recent_tree = ttk.Treeview(bottom_frame, columns=columns, 
                                      show="headings", height=5)
        
        self.recent_tree.heading("comp_no", text="Rek. Szám")
        self.recent_tree.heading("customer", text="Vásárló")
        self.recent_tree.heading("brand", text="Márka")
        self.recent_tree.heading("status", text="Státusz")
        
        self.recent_tree.column("comp_no", width=120)
        self.recent_tree.column("customer", width=200)
        self.recent_tree.column("brand", width=120)
        self.recent_tree.column("status", width=100)
        
        self.recent_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Inicializáljuk az aktuális hónapot
        self.current_month = datetime.date.today().month
        self.current_year = datetime.date.today().year
        
        # A dashboard első betöltése
        self.refresh_dashboard()

    def create_stat_panel(self, parent, title, value):
        """Létrehoz egy statisztikai panelt"""
        frame = ttk.Frame(parent, style='Stat.TFrame')
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        title_label = ttk.Label(frame, text=title, style='Bold.TLabel')
        title_label.pack(pady=(5, 0))
        
        value_var = tk.StringVar(value=value)
        value_label = ttk.Label(frame, textvariable=value_var, 
                               font=('Arial', 24, 'bold'), foreground='#4B8BBE')
        value_label.pack(pady=(0, 5))
        
        return value_var

    def refresh_dashboard(self):
        """Frissíti a dashboard adatait"""
        # Statisztikák lekérése
        stats = self.data_manager.get_stats()
        
        # Statisztikai kártyák frissítése
        self.stat_total.set(str(stats["total"]))
        self.stat_open.set(str(stats["open"]))
        self.stat_closed.set(str(stats["closed"]))
        self.stat_overdue.set(str(stats["overdue"]))
        self.stat_pending.set(str(stats["pending_manufacturer"]))
        
        # Naptár frissítése
        self.refresh_calendar()
        
        # Márka eloszlás frissítése
        self.refresh_brand_stats(stats["brands"])
        
        # Legutóbbi reklamációk frissítése
        self.refresh_recent_complaints(stats["recent"])
    
    def refresh_calendar(self):
        """A naptár nézet frissítése"""
        # Meglévő naptárelemek törlése
        for widget in self.calendar_content.winfo_children():
            widget.destroy()
        
        # Aktuális hónap adatai
        year = self.current_year
        month = self.current_month
        self.month_var.set(f"{year}. {calendar.month_name[month]}")
        
        # A hónap napjai
        month_days = calendar.monthcalendar(year, month)
        
        # Hét napjai fejléc
        days = ["H", "K", "Sze", "Cs", "P", "Szo", "V"]
        day_frame = ttk.Frame(self.calendar_content)
        day_frame.pack(fill=tk.X)
        
        for i, day in enumerate(days):
            day_label = ttk.Label(day_frame, text=day, style='CalHeader.TLabel',
                                 width=5, anchor='center')
            day_label.grid(row=0, column=i, sticky='nsew', padx=1, pady=1)
        
        # Határidős események lekérése
        deadlines = self.get_month_deadlines(year, month)
        
        # Mai nap
        today = datetime.date.today()
        
        # Naptár napok kirajzolása
        for week_idx, week in enumerate(month_days):
            week_frame = ttk.Frame(self.calendar_content)
            week_frame.pack(fill=tk.X)
            
            for day_idx, day in enumerate(week):
                if day == 0:
                    # Nincs nap ebben a hónapban
                    empty_label = ttk.Label(week_frame, text="", style='CalDay.TLabel',
                                          width=5, anchor='center')
                    empty_label.grid(row=0, column=day_idx, sticky='nsew', padx=1, pady=1)
                else:
                    # Megfelelő stílus kiválasztása
                    day_style = 'CalDay.TLabel'
                    day_date = datetime.date(year, month, day)
                    
                    # Mai nap?
                    if day_date == today:
                        day_style = 'CalToday.TLabel'
                    # Van határidő ezen a napon?
                    elif day in deadlines:
                        day_style = 'CalEvent.TLabel'
                    
                    day_label = ttk.Label(week_frame, text=str(day), style=day_style,
                                        width=5, anchor='center')
                    day_label.grid(row=0, column=day_idx, sticky='nsew', padx=1, pady=1)
                    
                    # Tooltip hozzáadása ha van esemény
                    if day in deadlines:
                        event_text = "\n".join([f"{comp_no}: {desc}" for comp_no, desc in deadlines[day]])
                        self.create_tooltip(day_label, event_text)
    
    def get_month_deadlines(self, year, month):
        """Visszaadja az adott hónap határidőit"""
        deadlines = {}
        today = datetime.date.today()
        
        for comp_no, comp_data in self.data_manager.complaints.items():
            # Csak nyitott reklamációk
            if comp_data.get("status", "open") != "open":
                continue
                
            # Saját határidő
            start = comp_data.get("start_date")
            dl_days = comp_data.get("deadline_days")
            if start and dl_days:
                try:
                    start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                    days_passed = int(dl_days)
                    deadline_date = start_date + datetime.timedelta(days=days_passed)
                    
                    # Csak az adott hónap határidői
                    if deadline_date.year == year and deadline_date.month == month:
                        day = deadline_date.day
                        desc = f"Saját határidő: {comp_data.get('customer', '')}"
                        
                        if day not in deadlines:
                            deadlines[day] = []
                        deadlines[day].append((comp_no, desc))
                except:
                    pass
            
            # Gyártói határidő
            man_sent = comp_data.get("manufacturer_sent_date", None)
            man_dl = comp_data.get("manufacturer_deadline_days", None)
            if man_sent and man_dl:
                try:
                    man_sent_date = datetime.datetime.strptime(man_sent, "%Y-%m-%d").date()
                    man_days = int(man_dl)
                    man_deadline_date = man_sent_date + datetime.timedelta(days=man_days)
                    
                    # Csak az adott hónap határidői
                    if man_deadline_date.year == year and man_deadline_date.month == month:
                        day = man_deadline_date.day
                        desc = f"Gyártói határidő: {comp_data.get('brand', '')}"
                        
                        if day not in deadlines:
                            deadlines[day] = []
                        deadlines[day].append((comp_no, desc))
                except:
                    pass
        
        return deadlines
    
    def create_tooltip(self, widget, text):
        """Tooltip létrehozása"""
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25
            
            # Tooltip ablak
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            
            label = ttk.Label(self.tooltip, text=text, background="#2B2B2B",
                             foreground="white", relief="solid", borderwidth=1,
                             padding=5, wraplength=200)
            label.pack()
            
        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
        
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
    
    def change_month(self, direction):
        """Hónap váltása a naptárban"""
        self.current_month += direction
        
        # Év váltás szükséges?
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        elif self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        
        # Naptár frissítése
        self.refresh_calendar()
    
    def refresh_brand_stats(self, brands_data):
        """Márka statisztikák frissítése"""
        # Meglévő elemek törlése
        for widget in self.brands_content.winfo_children():
            widget.destroy()
        
        if not brands_data:
            empty_label = ttk.Label(self.brands_content, text="Nincs adat", style='TLabel')
            empty_label.pack()
            return
        
        # Összesítés a százalékokhoz
        total = sum(brands_data.values())
        
        # Márka adatok rendezése érték szerint csökkenő sorrendben
        sorted_brands = sorted(brands_data.items(), key=lambda x: x[1], reverse=True)
        
        # Maximális érték a skálázáshoz
        max_value = sorted_brands[0][1] if sorted_brands else 0
        
        # Márka statisztikák kirajzolása
        for brand, count in sorted_brands:
            frame = ttk.Frame(self.brands_content)
            frame.pack(fill=tk.X, pady=3)
            
            # Százalék számítás
            percent = (count / total) * 100 if total > 0 else 0
            
            # Márka címke
            brand_label = ttk.Label(frame, text=brand, width=15, anchor='w', style='Bold.TLabel')
            brand_label.pack(side=tk.LEFT)
            
            # Progress bar keret
            bar_frame = ttk.Frame(frame, height=20)
            bar_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # Kitöltött rész
            bar_width = int((count / max_value) * 100) if max_value > 0 else 0
            bar = tk.Frame(bar_frame, bg="#4B8BBE", height=20, width=bar_width*2)
            bar.pack(side=tk.LEFT, anchor='w')
            
            # Érték és százalék
            value_label = ttk.Label(frame, text=f"{count} ({percent:.1f}%)", width=15, anchor='e')
            value_label.pack(side=tk.RIGHT)
    
    def refresh_recent_complaints(self, recent_data):
        """Legutóbbi reklamációk frissítése"""
        # Treeview törlése
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
        
        # Adatok feltöltése
        for item in recent_data:
            self.recent_tree.insert("", tk.END, values=(
                item["comp_no"],
                item["customer"],
                item["brand"],
                item["status"]
            ))
            
        # Kattintás esemény - átugrás a főnézetbe
        self.recent_tree.bind("<Double-1>", self.on_recent_click)
    
    def on_recent_click(self, event):
        """Legutóbbi reklamációkra kattintás eseménykezelője"""
        selection = self.recent_tree.selection()
        if selection:
            item = self.recent_tree.item(selection[0])
            comp_no = item["values"][0]
            
            # Váltás a fő nézetre
            self.notebook.select(0)
            
            # Reklamáció keresése és kijelölése
            self.search_and_select_complaint(comp_no)
    
    def search_and_select_complaint(self, comp_no):
        """Reklamáció keresése és kijelölése a fő nézetben"""
        # Minden reklamáció betöltése
        self.refresh_tree()
        
        # Reklamáció keresése
        for item in self.tree.get_children():
            item_values = self.tree.item(item, "values")
            if item_values[0] == comp_no:
                # Kijelölés
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item)
                break

    # ----------------------------------------------------------------
    #                      FEJLETT KERESÉS
    # ----------------------------------------------------------------
    def open_advanced_search(self):
        """Fejlett keresési ablak megnyitása"""
        search_win = tk.Toplevel(self)
        search_win.title("Részletes keresés")
        search_win.geometry("600x500")
        search_win.configure(bg="#2B2B2B")
        search_win.transient(self)
        search_win.grab_set()
        
        # Főkeret létrehozása
        main_frame = ttk.Frame(search_win, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Fejléc
        header = ttk.Label(main_frame, text="Részletes keresés", style='Header.TLabel',
                          font=('Arial', 14, 'bold'))
        header.pack(pady=(0, 15))
        
        # Keresési feltételek
        criteria_frame = ttk.LabelFrame(main_frame, text="Keresési feltételek")
        criteria_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Funkció a mezők egységes megjelenítéséhez
        def create_search_field(parent, label_text, placeholder=""):
            field_frame = ttk.Frame(parent)
            field_frame.pack(fill=tk.X, pady=5)
            
            label = ttk.Label(field_frame, text=label_text, width=20, anchor='w', style='Bold.TLabel')
            label.pack(side=tk.LEFT)
            
            entry = tk.Entry(field_frame, bg="#4B4B4B", fg="white", insertbackground="white",
                            font=('Arial', 10), relief="flat", bd=5)
            if placeholder:
                entry.insert(0, placeholder)
                
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            return entry
        
        # Reklamáció szám
        rekl_entry = create_search_field(criteria_frame, "Reklamáció szám:")
        
        # Vásárló neve
        customer_entry = create_search_field(criteria_frame, "Vásárló neve:")
        
        # Termék neve
        product_entry = create_search_field(criteria_frame, "Termék neve:")
        
        # Márka ComboBox
        brand_frame = ttk.Frame(criteria_frame)
        brand_frame.pack(fill=tk.X, pady=5)
        
        brand_label = ttk.Label(brand_frame, text="Márka:", width=20, anchor='w', style='Bold.TLabel')
        brand_label.pack(side=tk.LEFT)
        
        brand_var = tk.StringVar()
        brand_combo = ttk.Combobox(brand_frame, textvariable=brand_var)
        brand_combo['values'] = [""] + BRAND_OPTIONS
        brand_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Státusz ComboBox
        status_frame = ttk.Frame(criteria_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        status_label = ttk.Label(status_frame, text="Státusz:", width=20, anchor='w', style='Bold.TLabel')
        status_label.pack(side=tk.LEFT)
        
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(status_frame, textvariable=status_var)
        status_combo['values'] = ["", "open", "closed"]
        status_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Határidő intervallum
        deadline_frame = ttk.LabelFrame(criteria_frame, text="Határidő intervallum")
        deadline_frame.pack(fill=tk.X, pady=10, padx=5)
        
        date_frame = ttk.Frame(deadline_frame)
        date_frame.pack(fill=tk.X, pady=5)
        
        from_label = ttk.Label(date_frame, text="Kezdete:", style='Bold.TLabel')
        from_label.pack(side=tk.LEFT, padx=5)
        
        from_entry = tk.Entry(date_frame, bg="#4B4B4B", fg="white", insertbackground="white",
                             font=('Arial', 10), relief="flat", bd=5, width=12)
        from_entry.insert(0, "YYYY-MM-DD")
        from_entry.pack(side=tk.LEFT, padx=5)
        
        to_label = ttk.Label(date_frame, text="Vége:", style='Bold.TLabel')
        to_label.pack(side=tk.LEFT, padx=5)
        
        to_entry = tk.Entry(date_frame, bg="#4B4B4B", fg="white", insertbackground="white",
                           font=('Arial', 10), relief="flat", bd=5, width=12)
        to_entry.insert(0, "YYYY-MM-DD")
        to_entry.pack(side=tk.LEFT, padx=5)
        
        # Extra feltételek
        extra_frame = ttk.Frame(criteria_frame)
        extra_frame.pack(fill=tk.X, pady=10)
        
        overdue_var = tk.BooleanVar()
        overdue_check = ttk.Checkbutton(extra_frame, text="Csak határidőn túli reklamációk",
                                       variable=overdue_var)
        overdue_check.pack(anchor='w')
        
        pending_var = tk.BooleanVar()
        pending_check = ttk.Checkbutton(extra_frame, text="Csak függő gyártói válaszok",
                                      variable=pending_var)
        pending_check.pack(anchor='w')
        
        # Gombok
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        def perform_search():
            # Keresési feltételek összegyűjtése
            criteria = {
                "rekl_szam": rekl_entry.get().strip(),
                "customer": customer_entry.get().strip(),
                "product": product_entry.get().strip(),
                "brand": brand_var.get(),
                "status": status_var.get(),
                "from_date": from_entry.get() if from_entry.get() != "YYYY-MM-DD" else "",
                "to_date": to_entry.get() if to_entry.get() != "YYYY-MM-DD" else "",
                "overdue": overdue_var.get(),
                "pending": pending_var.get()
            }
            
            # Keresés végrehajtása
            self.advanced_search(criteria)
            search_win.destroy()
        
        reset_btn = ttk.Button(button_frame, text="Mezők törlése", command=lambda: [
            rekl_entry.delete(0, tk.END),
            customer_entry.delete(0, tk.END),
            product_entry.delete(0, tk.END),
            brand_var.set(""),
            status_var.set(""),
            from_entry.delete(0, tk.END),
            from_entry.insert(0, "YYYY-MM-DD"),
            to_entry.delete(0, tk.END),
            to_entry.insert(0, "YYYY-MM-DD"),
            overdue_var.set(False),
            pending_var.set(False)
        ])
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="Mégse", command=search_win.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        search_btn = ttk.Button(button_frame, text="Keresés", command=perform_search)
        search_btn.pack(side=tk.RIGHT, padx=5)
        
        # Enter lenyomására keresés
        search_win.bind('<Return>', lambda event: perform_search())
        
        # Esc billentyűre bezárás
        search_win.bind('<Escape>', lambda event: search_win.destroy())
        
        # Ablak középre pozicionálása
        search_win.update_idletasks()
        width = search_win.winfo_width()
        height = search_win.winfo_height()
        x = (search_win.winfo_screenwidth() // 2) - (width // 2)
        y = (search_win.winfo_screenheight() // 2) - (height // 2)
        search_win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def advanced_search(self, criteria):
        """Részletes keresés végrehajtása"""
        results = {}
        today = datetime.date.today()
        
        for comp_no, comp_data in self.data_manager.complaints.items():
            # Alapvető keresési feltételek ellenőrzése
            if criteria["rekl_szam"] and criteria["rekl_szam"].lower() not in comp_no.lower():
                continue
            
            if criteria["customer"] and criteria["customer"].lower() not in comp_data.get("customer", "").lower():
                continue
                
            if criteria["product"] and criteria["product"].lower() not in comp_data.get("product_name", "").lower():
                continue
                
            if criteria["brand"] and criteria["brand"] != comp_data.get("brand", ""):
                continue
                
            if criteria["status"] and criteria["status"] != comp_data.get("status", "open"):
                continue
            
            # Határidőn túli ellenőrzése
            if criteria["overdue"]:
                start = comp_data.get("start_date")
                dl_days = comp_data.get("deadline_days")
                is_overdue = False
                
                if start and dl_days:
                    try:
                        start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                        days_passed = (today - start_date).days
                        days_left = int(dl_days) - days_passed
                        
                        if days_left < 0 and comp_data.get("status", "open") == "open":
                            is_overdue = True
                    except:
                        pass
                
                if not is_overdue:
                    continue
            
            # Függő gyártói válasz ellenőrzése
            if criteria["pending"]:
                man_sent = comp_data.get("manufacturer_sent_date", None)
                man_resp = comp_data.get("manufacturer_response", "")
                
                if not man_sent or man_resp or comp_data.get("status", "open") != "open":
                    continue
            
            # Dátum intervallum ellenőrzése
            if criteria["from_date"] or criteria["to_date"]:
                start = comp_data.get("start_date")
                if not start:
                    continue
                    
                try:
                    start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                    
                    if criteria["from_date"]:
                        try:
                            from_date = datetime.datetime.strptime(criteria["from_date"], "%Y-%m-%d").date()
                            if start_date < from_date:
                                continue
                        except:
                            pass
                    
                    if criteria["to_date"]:
                        try:
                            to_date = datetime.datetime.strptime(criteria["to_date"], "%Y-%m-%d").date()
                            if start_date > to_date:
                                continue
                        except:
                            pass
                except:
                    continue
            
            # Ha minden feltétel teljesül, hozzáadjuk az eredményekhez
            results[comp_no] = comp_data
        
        # Eredmények megjelenítése
        self.display_search_results(results)
    
    def display_search_results(self, results):
        """Keresési eredmények megjelenítése"""
        # Treeview törlése
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Eredmények kiírása
        count = 0
        for comp_no, comp_data in results.items():
            status_text = comp_data.get("status", "open")
            
            # Hátralevő napok számítása
            deadline_text = self.calculate_days_left(comp_data)
            
            if self.is_manufacturer_response_overdue(comp_data):
                status_text += " [Gyártói válasz késik]"
                
            self.tree.insert(
                "",
                tk.END,
                values=(
                    comp_no,
                    comp_data.get("customer", ""),
                    comp_data.get("product_name", ""),
                    comp_data.get("brand", ""),
                    status_text,
                    deadline_text
                )
            )
            count += 1
        
        # Állapotsor frissítése
        self.status_var.set(f"Keresési eredmény: {count} találat")
    
    def calculate_days_left(self, comp_data):
        """Kiszámítja a hátralevő napokat"""
        start = comp_data.get("start_date")
        dl_days = comp_data.get("deadline_days")
        
        if not start or not dl_days or comp_data.get("status", "open") == "closed":
            return "N/A"
            
        try:
            start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
            today = datetime.date.today()
            days_passed = (today - start_date).days
            days_left = int(dl_days) - days_passed
            
            if days_left < 0:
                return f"Lejárt ({abs(days_left)} napja)"
            else:
                return f"{days_left} nap"
        except:
            return "N/A"

    # ----------------------------------------------------------------
    #                EXPORTÁLÁSI FUNKCIÓK
    # ----------------------------------------------------------------
    def show_export_options(self):
        """Exportálási lehetőségek megjelenítése"""
        # Ellenőrizzük, hogy van-e reklamáció
        if not self.data_manager.complaints:
            messagebox.showinfo("Információ", "Nincs exportálható reklamáció.")
            return
        
        export_win = tk.Toplevel(self)
        export_win.title("Exportálás")
        export_win.geometry("400x300")
        export_win.configure(bg="#2B2B2B")
        export_win.transient(self)
        export_win.grab_set()
        
        # Főkeret létrehozása
        main_frame = ttk.Frame(export_win, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Fejléc
        header = ttk.Label(main_frame, text="Exportálási beállítások", style='Header.TLabel')
        header.pack(pady=(0, 15))
        
        # Exportálási formátum
        format_frame = ttk.LabelFrame(main_frame, text="Formátum")
        format_frame.pack(fill=tk.X, pady=10)
        
        format_var = tk.StringVar(value="csv")
        
        for key, value in self.export_formats.items():
            rb = ttk.Radiobutton(format_frame, text=value["name"], variable=format_var, value=key)
            rb.pack(anchor="w", pady=5, padx=10)
        
        # Export tartalom
        content_frame = ttk.LabelFrame(main_frame, text="Exportálandó adatok")
        content_frame.pack(fill=tk.X, pady=10)
        
        all_var = tk.BooleanVar(value=True)
        open_var = tk.BooleanVar(value=False)
        filtered_var = tk.BooleanVar(value=False)
        
        all_rb = ttk.Radiobutton(content_frame, text="Összes reklamáció", 
                                variable=all_var, value=True,
                                command=lambda: [open_var.set(False), filtered_var.set(False)])
        all_rb.pack(anchor="w", pady=5, padx=10)
        
        open_rb = ttk.Radiobutton(content_frame, text="Csak nyitott reklamációk", 
                                 variable=open_var, value=True,
                                 command=lambda: [all_var.set(False), filtered_var.set(False)])
        open_rb.pack(anchor="w", pady=5, padx=10)
        
        filtered_rb = ttk.Radiobutton(content_frame, text="Csak a szűrt lista", 
                                     variable=filtered_var, value=True,
                                     command=lambda: [all_var.set(False), open_var.set(False)])
        filtered_rb.pack(anchor="w", pady=5, padx=10)
        
        # Gombok
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        def perform_export():
            # Exportálási feltételek összegyűjtése
            export_format = format_var.get()
            
            # Exportálandó adatok meghatározása
            if all_var.get():
                export_data = self.data_manager.complaints
            elif open_var.get():
                export_data = {k: v for k, v in self.data_manager.complaints.items() 
                              if v.get("status", "open") == "open"}
            else:  # Szűrt lista
                export_data = {}
                for item in self.tree.get_children():
                    item_values = self.tree.item(item, "values")
                    comp_no = item_values[0]
                    if comp_no in self.data_manager.complaints:
                        export_data[comp_no] = self.data_manager.complaints[comp_no]
            
            # Exportálás végrehajtása
            if export_format in self.export_formats:
                export_func = self.export_formats[export_format]["func"]
                export_func(export_data)
            
            export_win.destroy()
        
        cancel_btn = ttk.Button(button_frame, text="Mégse", command=export_win.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        export_btn = ttk.Button(button_frame, text="Exportálás", command=perform_export)
        export_btn.pack(side=tk.RIGHT, padx=5)
        
        # Esc billentyűre bezárás
        export_win.bind('<Escape>', lambda event: export_win.destroy())
        
        # Ablak középre pozicionálása
        export_win.update_idletasks()
        width = export_win.winfo_width()
        height = export_win.winfo_height()
        x = (export_win.winfo_screenwidth() // 2) - (width // 2)
        y = (export_win.winfo_screenheight() // 2) - (height // 2)
        export_win.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    def export_to_csv(self, data):
        """Exportálás CSV formátumba"""
        if not data:
            messagebox.showinfo("Információ", "Nincs exportálható adat.")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV fájl", "*.csv"), ("Minden fájl", "*.*")],
            title="CSV fájl mentése"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                # CSV writer létrehozása
                writer = csv.writer(csv_file, delimiter=';')
                
                # Fejléc írása
                writer.writerow([
                    "Reklamáció szám", "Vásárló neve", "Lakcím", "Termék neve", 
                    "Márka", "Panasz leírás", "Státusz", "Gyártói válasz",
                    "Kezdési dátum", "Határidő (nap)", "Határidő dátum", "Hátralevő napok"
                ])
                
                # Adatok írása
                today = datetime.date.today()
                for comp_no, comp_data in data.items():
                    # Határidő számítás
                    deadline_date = "N/A"
                    days_left = "N/A"
                    start = comp_data.get("start_date")
                    dl_days = comp_data.get("deadline_days")
                    
                    if start and dl_days:
                        try:
                            start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                            deadline_date = (start_date + datetime.timedelta(days=int(dl_days))).strftime("%Y-%m-%d")
                            days_passed = (today - start_date).days
                            days_left = int(dl_days) - days_passed
                        except:
                            pass
                    
                    writer.writerow([
                        comp_no,
                        comp_data.get("customer", ""),
                        comp_data.get("customer_address", ""),
                        comp_data.get("product_name", ""),
                        comp_data.get("brand", ""),
                        comp_data.get("complaint_description", ""),
                        comp_data.get("status", "open"),
                        comp_data.get("manufacturer_response", ""),
                        start,
                        dl_days,
                        deadline_date,
                        days_left
                    ])
            
            messagebox.showinfo("Sikeres exportálás", f"A fájl elmentve: {file_path}")
            self.status_var.set(f"Exportálás kész: {file_path}")
            
            # Fájl megnyitása
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'posix':  # macOS és Linux
                    if os.uname().sysname == 'Darwin':  # macOS
                        subprocess.run(['open', file_path])
                    else:  # Linux
                        subprocess.run(['xdg-open', file_path])
            except:
                pass
                
        except Exception as e:
            messagebox.showerror("Exportálási hiba", f"Hiba az exportálás során: {str(e)}")
    
    def export_to_html(self, data):
        """Exportálás HTML formátumba"""
        if not data:
            messagebox.showinfo("Információ", "Nincs exportálható adat.")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML fájl", "*.html"), ("Minden fájl", "*.*")],
            title="HTML fájl mentése"
        )
        
        if not file_path:
            return
        
        try:
            # HTML fájl tartalom létrehozása
            html_content = []
            html_content.append("<!DOCTYPE html>")
            html_content.append("<html lang='hu'>")
            html_content.append("<head>")
            html_content.append("<meta charset='utf-8'>")
            html_content.append("<title>Reklamációk listája</title>")
            html_content.append("<style>")
            html_content.append("body { font-family: Arial, sans-serif; margin: 20px; }")
            html_content.append("h1 { color: #306998; }")
            html_content.append("table { border-collapse: collapse; width: 100%; margin-top: 20px; }")
            html_content.append("th { background-color: #306998; color: white; text-align: left; padding: 8px; }")
            html_content.append("td { border: 1px solid #ddd; padding: 8px; }")
            html_content.append("tr:nth-child(even) { background-color: #f2f2f2; }")
            html_content.append(".overdue { color: red; }")
            html_content.append(".warning { color: orange; }")
            html_content.append(".ok { color: green; }")
            html_content.append("</style>")
            html_content.append("</head>")
            html_content.append("<body>")
            html_content.append("<h1>Reklamációk listája</h1>")
            
            # Exportálás időpontja
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            html_content.append(f"<p>Exportálás időpontja: {now}</p>")
            
            # Táblázat létrehozása
            html_content.append("<table>")
            html_content.append("<tr>")
            html_content.append("<th>Reklamáció szám</th>")
            html_content.append("<th>Vásárló neve</th>")
            html_content.append("<th>Termék neve</th>")
            html_content.append("<th>Márka</th>")
            html_content.append("<th>Státusz</th>")
            html_content.append("<th>Kezdési dátum</th>")
            html_content.append("<th>Határidő</th>")
            html_content.append("</tr>")
            
            # Adatok írása a táblázatba
            today = datetime.date.today()
            for comp_no, comp_data in data.items():
                # Határidő számítás
                deadline_date = "N/A"
                days_left = "N/A"
                days_left_class = ""
                start = comp_data.get("start_date")
                dl_days = comp_data.get("deadline_days")
                
                if start and dl_days:
                    try:
                        start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                        deadline_date = (start_date + datetime.timedelta(days=int(dl_days))).strftime("%Y-%m-%d")
                        days_passed = (today - start_date).days
                        days_left = int(dl_days) - days_passed
                        
                        if days_left < 0:
                            days_left_class = "overdue"
                        elif days_left <= 5:
                            days_left_class = "warning"
                        else:
                            days_left_class = "ok"
                    except:
                        pass
                
                status = comp_data.get("status", "open")
                
                html_content.append("<tr>")
                html_content.append(f"<td>{comp_no}</td>")
                html_content.append(f"<td>{comp_data.get('customer', '')}</td>")
                html_content.append(f"<td>{comp_data.get('product_name', '')}</td>")
                html_content.append(f"<td>{comp_data.get('brand', '')}</td>")
                html_content.append(f"<td>{status}</td>")
                html_content.append(f"<td>{start}</td>")
                
                if days_left_class and status == "open":
                    html_content.append(f"<td class='{days_left_class}'>{deadline_date} ({days_left} nap)</td>")
                else:
                    html_content.append(f"<td>{deadline_date}</td>")
                
                html_content.append("</tr>")
            
            html_content.append("</table>")
            html_content.append("</body>")
            html_content.append("</html>")
            
            # HTML fájl mentése
            with open(file_path, 'w', encoding='utf-8') as html_file:
                html_file.write("\n".join(html_content))
            
            messagebox.showinfo("Sikeres exportálás", f"A fájl elmentve: {file_path}")
            self.status_var.set(f"Exportálás kész: {file_path}")
            
            # Fájl megnyitása böngészőben
            webbrowser.open(file_path)
                
        except Exception as e:
            messagebox.showerror("Exportálási hiba", f"Hiba az exportálás során: {str(e)}")
    
    def export_to_text(self, data):
        """Exportálás szöveges formátumba"""
        if not data:
            messagebox.showinfo("Információ", "Nincs exportálható adat.")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Szöveges fájl", "*.txt"), ("Minden fájl", "*.*")],
            title="Szöveges fájl mentése"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as txt_file:
                # Fejléc
                txt_file.write("REKLAMÁCIÓK LISTÁJA\n")
                txt_file.write("=" * 50 + "\n\n")
                
                # Exportálás időpontja
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                txt_file.write(f"Exportálás időpontja: {now}\n\n")
                
                # Adatok írása
                today = datetime.date.today()
                for comp_no, comp_data in data.items():
                    txt_file.write(f"Reklamáció szám: {comp_no}\n")
                    txt_file.write("-" * 30 + "\n")
                    txt_file.write(f"Vásárló neve: {comp_data.get('customer', '')}\n")
                    txt_file.write(f"Lakcím: {comp_data.get('customer_address', '')}\n")
                    txt_file.write(f"Termék neve: {comp_data.get('product_name', '')}\n")
                    txt_file.write(f"Márka: {comp_data.get('brand', '')}\n")
                    txt_file.write(f"Panasz leírás: {comp_data.get('complaint_description', '')}\n")
                    txt_file.write(f"Státusz: {comp_data.get('status', 'open')}\n")
                    
                    # Határidő számítás
                    start = comp_data.get("start_date")
                    dl_days = comp_data.get("deadline_days")
                    
                    if start and dl_days:
                        txt_file.write(f"Kezdési dátum: {start}\n")
                        txt_file.write(f"Határidő (nap): {dl_days}\n")
                        
                        try:
                            start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                            deadline_date = (start_date + datetime.timedelta(days=int(dl_days))).strftime("%Y-%m-%d")
                            days_passed = (today - start_date).days
                            days_left = int(dl_days) - days_passed
                            
                            txt_file.write(f"Határidő dátum: {deadline_date}\n")
                            
                            if comp_data.get("status", "open") == "open":
                                if days_left < 0:
                                    txt_file.write(f"Hátralevő napok: LEJÁRT! ({abs(days_left)} napja)\n")
                                else:
                                    txt_file.write(f"Hátralevő napok: {days_left}\n")
                        except:
                            pass
                    
                    # Gyártói válasz
                    man_resp = comp_data.get("manufacturer_response", "")
                    if man_resp:
                        txt_file.write(f"Gyártói válasz: {man_resp}\n")
                    else:
                        txt_file.write("Gyártói válasz: Nincs\n")
                    
                    # Csatolt fájlok
                    photos = comp_data.get("photos", [])
                    if photos:
                        txt_file.write("Csatolt fájlok:\n")
                        for photo in photos:
                            txt_file.write(f"  - {photo}\n")
                    
                    txt_file.write("\n" + "=" * 50 + "\n\n")
            
            messagebox.showinfo("Sikeres exportálás", f"A fájl elmentve: {file_path}")
            self.status_var.set(f"Exportálás kész: {file_path}")
            
            # Fájl megnyitása
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'posix':  # macOS és Linux
                    if os.uname().sysname == 'Darwin':  # macOS
                        subprocess.run(['open', file_path])
                    else:  # Linux
                        subprocess.run(['xdg-open', file_path])
            except:
                pass
                
        except Exception as e:
            messagebox.showerror("Exportálási hiba", f"Hiba az exportálás során: {str(e)}")

    # ----------------------------------------------------------------
    #                REKLAMÁCIÓ TÖRLÉSE (ÚJ FUNKCIÓ)
    # ----------------------------------------------------------------
    def delete_complaint(self):
        comp_no = self.get_selected_complaint_number()
        if not comp_no:
            messagebox.showerror("Hiba", "Nincs kiválasztva reklamáció!")
            return

        comp = self.data_manager.complaints.get(comp_no, None)
        if not comp:
            messagebox.showerror("Hiba", "A kiválasztott reklamáció nem létezik.")
            return

        confirm = messagebox.askyesno("Megerősítés",
                                      f"Biztosan törlöd a(z) {comp_no} reklamációt az összes melléklettel együtt?")
        if confirm:
            photos = comp.get("photos", [])
            for photo in photos:
                photo_path = os.path.join(PHOTOS_DIR, photo)
                if os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                    except:
                        pass

            del self.data_manager.complaints[comp_no]
            self.data_manager.save_complaints()
            messagebox.showinfo("Siker", f"A(z) {comp_no} reklamáció törölve.")
            self.refresh_tree()
            self.status_var.set(f"Reklamáció törölve: {comp_no}")

    # ----------------------------------------------------------------
    #                    HATÁRIDŐK ELLENŐRZÉSE
    # ----------------------------------------------------------------
    def check_deadlines(self):
        today = datetime.date.today()
        warnings = []

        for comp_no, comp_data in self.data_manager.complaints.items():
            # Saját határidő
            start = comp_data.get("start_date")
            dl_days = comp_data.get("deadline_days")
            if start and dl_days:
                try:
                    start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                    days_passed = (today - start_date).days
                    days_left = int(dl_days) - days_passed
                    if days_left <= 5:
                        warnings.append(f"[Saját határidő] {comp_no} lejár {days_left} napon belül!")
                except:
                    pass

            # Gyártói határidő
            man_sent = comp_data.get("manufacturer_sent_date", None)
            man_dl = comp_data.get("manufacturer_deadline_days", None)
            man_resp = comp_data.get("manufacturer_response", "")
            if man_sent and man_dl and (not man_resp):
                try:
                    man_sent_date = datetime.datetime.strptime(man_sent, "%Y-%m-%d").date()
                    man_days_passed = (today - man_sent_date).days
                    man_days_left = int(man_dl) - man_days_passed
                    if man_days_left < 0:
                        warnings.append(f"[Gyártói válasz késik] {comp_no} határideje {abs(man_days_left)} nappal ezelőtt lejárt!")
                except:
                    pass

        if warnings:
            warning_text = "\n".join(warnings)
            messagebox.showwarning("Közelgő / lejárt határidők!", warning_text)
            # Állapotsorban is jelezzük
            self.status_var.set(f"Figyelem: {len(warnings)} határidő közeleg vagy lejárt!")

    # ----------------------------------------------------------------
    #                  LISTA + KERESÉS + STÁTUS KIÍRÁS
    # ----------------------------------------------------------------
    def refresh_tree(self, filter_query=None):
        for row in self.tree.get_children():
            self.tree.delete(row)

        count = 0
        for comp_no, comp_data in self.data_manager.complaints.items():
            if filter_query:
                q = filter_query.lower()
                if (q not in comp_no.lower()) and (q not in comp_data["customer"].lower()):
                    continue

            status_text = comp_data.get("status", "open")
            if self.is_manufacturer_response_overdue(comp_data):
                status_text += " [Gyártói válasz késik]"
                
            # Határidő szöveg
            deadline_text = self.calculate_days_left(comp_data)

            self.tree.insert(
                "",
                tk.END,
                values=(
                    comp_no,
                    comp_data.get("customer", ""),
                    comp_data.get("product_name", ""),
                    comp_data.get("brand", ""),
                    status_text,
                    deadline_text
                )
            )
            count += 1
        
        if filter_query:
            self.status_var.set(f"Szűrés eredménye: {count} találat")
        else:
            self.status_var.set(f"Összes reklamáció: {count}")

    def is_manufacturer_response_overdue(self, comp_data):
        man_sent = comp_data.get("manufacturer_sent_date", None)
        man_dl = comp_data.get("manufacturer_deadline_days", None)
        man_resp = comp_data.get("manufacturer_response", "")
        if not man_sent or not man_dl:
            return False
        if man_resp:
            return False
        try:
            today = datetime.date.today()
            man_sent_date = datetime.datetime.strptime(man_sent, "%Y-%m-%d").date()
            days_passed = (today - man_sent_date).days
            if days_passed > int(man_dl):
                return True
        except:
            pass
        return False

    def get_selected_complaint_number(self):
        selection = self.tree.selection()
        if not selection:
            return None
        row_id = selection[0]
        values = self.tree.item(row_id, "values")
        comp_no = values[0]
        return comp_no

    def search_complaints(self):
        query = self.search_entry.get().strip()
        if query:
            self.refresh_tree(filter_query=query)
        else:
            self.refresh_tree()

    # ----------------------------------------------------------------
    #              ÚJ REKLAMÁCIÓ FELVÉTELE
    # ----------------------------------------------------------------
    def add_complaint_window(self):
        win = tk.Toplevel(self)
        win.title("Új Reklamáció")
        win.geometry("500x700")
        win.configure(bg="#2B2B2B")
        win.resizable(False, True)
        win.transient(self)  # Az ablak a főablakhoz kapcsolódik
        win.grab_set()  # Modális ablak

        # Főkeret görgetősávval
        main_frame = tk.Frame(win, bg="#2B2B2B", bd=0)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Canvas és scrollbar a gördítéshez
        canvas = tk.Canvas(main_frame, bg="#2B2B2B", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        
        # Scrollozható keret
        scrollable_frame = tk.Frame(canvas, bg="#2B2B2B", bd=0)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Funkciók létrehozása a mezők konzisztens megjelenéséhez
        def create_label_entry(parent, label_text, default_value=""):
            frame = tk.Frame(parent, bg="#2B2B2B", pady=5)
            frame.pack(fill=tk.X)
            
            label = tk.Label(frame, text=label_text, bg="#2B2B2B", fg="white", 
                             font=("Arial", 10, "bold"), anchor="w")
            label.pack(fill=tk.X)
            
            entry = tk.Entry(frame, bg="#4B4B4B", fg="white", insertbackground="white",
                            font=("Arial", 10), relief="flat", bd=5)
            if default_value:
                entry.insert(0, default_value)
            entry.pack(fill=tk.X, pady=(2, 5))
            
            return entry
        
        def create_label_combobox(parent, label_text, values, default_value=""):
            frame = tk.Frame(parent, bg="#2B2B2B", pady=5)
            frame.pack(fill=tk.X)
            
            label = tk.Label(frame, text=label_text, bg="#2B2B2B", fg="white", 
                             font=("Arial", 10, "bold"), anchor="w")
            label.pack(fill=tk.X)
            
            var = tk.StringVar(value=default_value)
            combo = ttk.Combobox(frame, textvariable=var, values=values)
            combo.pack(fill=tk.X, pady=(2, 5))
            
            return var, combo
        
        # Fejléc
        header = tk.Label(scrollable_frame, text="Új Reklamáció Felvétele", 
                         bg="#2B2B2B", fg="white", font=("Arial", 14, "bold"))
        header.pack(pady=(0, 15))
        
        # Alapadatok szakasz
        alapadatok_frame = ttk.LabelFrame(scrollable_frame, text="Alapadatok", padding=10)
        alapadatok_frame.pack(fill=tk.X, pady=10)
        
        entry_comp_no = create_label_entry(alapadatok_frame, "Reklamáció Szám:")
        entry_customer = create_label_entry(alapadatok_frame, "Vásárló Név:")
        entry_address = create_label_entry(alapadatok_frame, "Lakcím:")
        entry_product = create_label_entry(alapadatok_frame, "Termék Név:")
        
        brand_var, _ = create_label_combobox(alapadatok_frame, "Márka:", BRAND_OPTIONS)
        
        entry_desc = create_label_entry(alapadatok_frame, "Panasz leírás (opcionális):")
        
        # Határidők szakasz
        hataridok_frame = ttk.LabelFrame(scrollable_frame, text="Határidők", padding=10)
        hataridok_frame.pack(fill=tk.X, pady=10)
        
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        start_date_entry = create_label_entry(hataridok_frame, "(Saját) Ügyintézés kezdete (YYYY-MM-DD):", today_str)
        deadline_entry = create_label_entry(hataridok_frame, "(Saját) Hány nap a határidő?", "30")
        
        # Gyártói szakasz
        gyartoi_frame = ttk.LabelFrame(scrollable_frame, text="Gyártói Információk", padding=10)
        gyartoi_frame.pack(fill=tk.X, pady=10)
        
        man_sent_entry = create_label_entry(gyartoi_frame, "Gyártónak elküldve (dátum, YYYY-MM-DD):")
        man_deadline_entry = create_label_entry(gyartoi_frame, "Gyártói válasz határideje (napokban):", "15")
        
        # Gomb szakasz
        button_frame = tk.Frame(scrollable_frame, bg="#2B2B2B", pady=15)
        button_frame.pack(fill=tk.X)
        
        def save_new_complaint():
            c_no = entry_comp_no.get().strip()
            cust = entry_customer.get().strip()
            address = entry_address.get().strip()
            prod = entry_product.get().strip()
            br = brand_var.get().strip()
            desc = entry_desc.get().strip()

            s_date = start_date_entry.get().strip()
            dl_days = deadline_entry.get().strip()
            man_sent_date = man_sent_entry.get().strip()
            man_dl_days = man_deadline_entry.get().strip()

            if not c_no or not cust or not prod or not br:
                messagebox.showerror("Hiba", "Kérlek tölts ki minden kötelező mezőt!")
                return

            if c_no in self.data_manager.complaints:
                messagebox.showerror("Hiba", f"A(z) {c_no} számú reklamáció már létezik!")
                return

            workshop_status = {
                "in_workshop": False,
                "repair_done": False,
                "returned_to_customer": False
            }
            inspection_at_customer = {
                "scheduled": None,
                "done": False
            }

            if br.lower() == "elitestrom":
                complaint_data = {
                    "customer": cust,
                    "customer_address": address,
                    "product_name": prod,
                    "brand": br,
                    "complaint_description": desc,
                    "status": "open",
                    "photos": [],
                    "manufacturer_response": None,
                    "additional_info": [],
                    "inspection": {
                        "szemle": False,
                        "műhelybe_hozva": False,
                        "megjavítva": False,
                        "vissza_vitt": False
                    },
                    "workshop_status": workshop_status,
                    "inspection_at_customer": inspection_at_customer,
                    "start_date": s_date,
                    "deadline_days": dl_days,
                    "manufacturer_sent_date": man_sent_date,
                    "manufacturer_deadline_days": man_dl_days
                }
            else:
                complaint_data = {
                    "customer": cust,
                    "customer_address": address,
                    "product_name": prod,
                    "brand": br,
                    "complaint_description": desc,
                    "status": "open",
                    "photos": [],
                    "manufacturer_response": None,
                    "additional_info": [],
                    "import_info": {
                        "szamlaszam": None,
                        "datum": None,
                        "iroda_feldolgozva": False
                    },
                    "workshop_status": workshop_status,
                    "inspection_at_customer": inspection_at_customer,
                    "start_date": s_date,
                    "deadline_days": dl_days,
                    "manufacturer_sent_date": man_sent_date,
                    "manufacturer_deadline_days": man_dl_days
                }

            self.data_manager.complaints[c_no] = complaint_data
            self.data_manager.save_complaints()
            self.refresh_tree()
            messagebox.showinfo("Siker", "Új reklamáció rögzítve!")
            self.status_var.set(f"Új reklamáció létrehozva: {c_no}")
            win.destroy()

        save_button = ttk.Button(button_frame, text="Reklamáció Mentése", command=save_new_complaint, padding=(10, 5))
        save_button.pack(pady=10)
        
        # Esc billentyű kezelése
        win.bind("<Escape>", lambda event: win.destroy())
        
        # Ablak középre pozicionálása
        win.update_idletasks()
        width = win.winfo_width()
        height = win.winfo_height()
        x = (win.winfo_screenwidth() // 2) - (width // 2)
        y = (win.winfo_screenheight() // 2) - (height // 2)
        win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    # ----------------------------------------------------------------
    #      RÉSZLETEK / MÓDOSÍTÁS (GÖRGETHETŐ) + GYÁRTÓI MEZŐK
    # ----------------------------------------------------------------
    def view_details_window(self):
        comp_no = self.get_selected_complaint_number()
        if not comp_no:
            messagebox.showerror("Hiba", "Nincs kiválasztva reklamáció!")
            return

        if comp_no not in self.data_manager.complaints:
            messagebox.showerror("Hiba", "A kiválasztott reklamáció nem létezik.")
            return

        comp_data = self.data_manager.complaints[comp_no]

        win = tk.Toplevel(self)
        win.title(f"Reklamáció: {comp_no}")
        win.geometry("800x700")
        win.configure(bg="#2B2B2B")
        win.transient(self)  # Az ablak a főablakhoz kapcsolódik
        win.grab_set()  # Modális ablak

        # Főkeret létrehozása
        main_container = tk.Frame(win, bg="#2B2B2B")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Fejléc
        header_frame = tk.Frame(main_container, bg="#2B2B2B")
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        header_label = tk.Label(header_frame, text=f"Reklamáció Részletei: {comp_no}", 
                               bg="#2B2B2B", fg="white", font=("Arial", 14, "bold"))
        header_label.pack(side=tk.LEFT)
        
        status_label = tk.Label(header_frame, text=f"Státusz: {comp_data.get('status','open')}", 
                               bg="#2B2B2B", fg="white", font=("Arial", 10))
        status_label.pack(side=tk.RIGHT)

        # Görgetősáv és keret
        container = ttk.Frame(main_container)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg="#2B2B2B", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Card.TFrame')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Adatbeviteli mezők létrehozása
        def create_field(parent, label_text, variable, width=50, padx=10, pady=5):
            field_frame = ttk.Frame(parent)
            field_frame.pack(fill=tk.X, padx=padx, pady=pady)
            
            label = ttk.Label(field_frame, text=label_text, style='Bold.TLabel')
            label.pack(anchor=tk.W)
            
            entry = tk.Entry(field_frame, textvariable=variable, width=width,
                            bg="#4B4B4B", fg="white", insertbackground="white",
                            font=('Arial', 10), relief="flat", bd=5)
            entry.pack(fill=tk.X, pady=(2, 0))
            
            return entry
        
        # Alapadatok szakasz
        alapadatok_frame = ttk.LabelFrame(scrollable_frame, text="Alapadatok", padding=10)
        alapadatok_frame.pack(fill=tk.X, padx=10, pady=10)

        cust_var = tk.StringVar(value=comp_data.get("customer",""))
        cust_entry = create_field(alapadatok_frame, "Vásárló neve:", cust_var)

        address_var = tk.StringVar(value=comp_data.get("customer_address",""))
        address_entry = create_field(alapadatok_frame, "Lakcím:", address_var)

        product_var = tk.StringVar(value=comp_data.get("product_name",""))
        product_entry = create_field(alapadatok_frame, "Termék neve:", product_var)

        # Márka combobox
        brand_frame = ttk.Frame(alapadatok_frame)
        brand_frame.pack(fill=tk.X, padx=10, pady=5)
        
        brand_label = ttk.Label(brand_frame, text="Márka:", style='Bold.TLabel')
        brand_label.pack(anchor=tk.W)
        
        brand_var = tk.StringVar(value=comp_data.get("brand",""))
        brand_combo = ttk.Combobox(brand_frame, textvariable=brand_var, values=BRAND_OPTIONS)
        brand_combo.pack(fill=tk.X, pady=(2, 0))

        complaint_var = tk.StringVar(value=comp_data.get("complaint_description",""))
        complaint_entry = create_field(alapadatok_frame, "Panasz leírás:", complaint_var)

        status_var = tk.StringVar(value=comp_data.get("status","open"))
        status_entry = create_field(alapadatok_frame, "Státusz:", status_var, width=20)

        # Gyártói válasz
        man_response_var = tk.StringVar(value=comp_data.get("manufacturer_response") or "")
        man_response_entry = create_field(alapadatok_frame, "Gyártó válasza:", man_response_var)

        # Határidők szakasz
        hataridok_frame = ttk.LabelFrame(scrollable_frame, text="Határidők", padding=10)
        hataridok_frame.pack(fill=tk.X, padx=10, pady=10)

        start_var = tk.StringVar(value=comp_data.get("start_date",""))
        start_entry = create_field(hataridok_frame, "(Saját) Ügyintézés kezdete (YYYY-MM-DD):", start_var, width=15)

        deadline_var = tk.StringVar(value=comp_data.get("deadline_days",""))
        deadline_entry = create_field(hataridok_frame, "(Saját) Határidő (napokban):", deadline_var, width=5)

        man_sent_var = tk.StringVar(value=comp_data.get("manufacturer_sent_date",""))
        man_sent_entry = create_field(hataridok_frame, "Gyártónak elküldve (YYYY-MM-DD):", man_sent_var, width=15)

        man_deadline_var = tk.StringVar(value=comp_data.get("manufacturer_deadline_days",""))
        man_deadline_entry = create_field(hataridok_frame, "Gyártói válasz határideje (napokban):", man_deadline_var, width=5)

        # Márkaspecifikus adatok (Elitestrom vagy Import)
        br = comp_data.get("brand", "").lower()
        is_elitestrom = (br == "elitestrom")
        i_vars = []

        if is_elitestrom:
            elitestrom_frame = ttk.LabelFrame(scrollable_frame, text="Elitestrom szemle állapotok", padding=10)
            elitestrom_frame.pack(fill=tk.X, padx=10, pady=10)
            
            insp = comp_data.get("inspection", {})

            def create_insp_row(parent, label_text, key):
                row_frame = ttk.Frame(parent)
                row_frame.pack(fill=tk.X, pady=3)
                
                label = ttk.Label(row_frame, text=label_text + ":", style='Bold.TLabel')
                label.pack(side=tk.LEFT, padx=(0, 10))
                
                var = tk.StringVar(value="igen" if insp.get(key, False) else "nem")
                combo = ttk.Combobox(row_frame, textvariable=var, values=["igen","nem"], width=7)
                combo.pack(side=tk.LEFT)
                
                return (var, key)

            for field in ["szemle", "műhelybe_hozva", "megjavítva", "vissza_vitt"]:
                i_vars.append(create_insp_row(elitestrom_frame, field, field))
        else:
            import_frame = ttk.LabelFrame(scrollable_frame, text="Import számla információ", padding=10)
            import_frame.pack(fill=tk.X, padx=10, pady=10)
            
            imp = comp_data.get("import_info", {})
            
            imp_grid = ttk.Frame(import_frame)
            imp_grid.pack(fill=tk.X)
            
            # Első sor
            row1 = ttk.Frame(imp_grid)
            row1.pack(fill=tk.X, pady=3)
            
            ttk.Label(row1, text="Számlaszám:", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
            inv_no_var = tk.StringVar(value=imp.get("szamlaszam") or "")
            inv_no_entry = tk.Entry(row1, textvariable=inv_no_var, width=25,
                                   bg="#4B4B4B", fg="white", insertbackground="white")
            inv_no_entry.pack(side=tk.LEFT)
            
            # Második sor
            row2 = ttk.Frame(imp_grid)
            row2.pack(fill=tk.X, pady=3)
            
            ttk.Label(row2, text="Dátum (YYYY-MM-DD):", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
            inv_date_var = tk.StringVar(value=imp.get("datum") or "")
            inv_date_entry = tk.Entry(row2, textvariable=inv_date_var, width=15,
                                     bg="#4B4B4B", fg="white", insertbackground="white")
            inv_date_entry.pack(side=tk.LEFT)
            
            # Harmadik sor
            row3 = ttk.Frame(imp_grid)
            row3.pack(fill=tk.X, pady=3)
            
            ttk.Label(row3, text="Iroda megküldte (igen/nem):", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
            office_var = tk.StringVar(value="igen" if imp.get("iroda_feldolgozva") else "nem")
            office_combo = ttk.Combobox(row3, textvariable=office_var, values=["igen","nem"], width=7)
            office_combo.pack(side=tk.LEFT)

        # Műhely szakasz
        workshop_frame = ttk.LabelFrame(scrollable_frame, text="Műhelyes státusz", padding=10)
        workshop_frame.pack(fill=tk.X, padx=10, pady=10)
        
        workshop = comp_data.get("workshop_status", {})
        
        ws_in_var = tk.StringVar(value="igen" if workshop.get("in_workshop", False) else "nem")
        ws_repair_var = tk.StringVar(value="igen" if workshop.get("repair_done", False) else "nem")
        ws_return_var = tk.StringVar(value="igen" if workshop.get("returned_to_customer", False) else "nem")
        
        # Grid elrendezés helyett egyszerű sorok
        row1 = ttk.Frame(workshop_frame)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="Behozva a műhelybe:", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        ws_in_combo = ttk.Combobox(row1, textvariable=ws_in_var, values=["igen","nem"], width=7)
        ws_in_combo.pack(side=tk.LEFT)
        
        row2 = ttk.Frame(workshop_frame)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="Megjavítva:", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        ws_repair_combo = ttk.Combobox(row2, textvariable=ws_repair_var, values=["igen","nem"], width=7)
        ws_repair_combo.pack(side=tk.LEFT)
        
        row3 = ttk.Frame(workshop_frame)
        row3.pack(fill=tk.X, pady=3)
        ttk.Label(row3, text="Visszaszállítva a vevőhöz:", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        ws_return_combo = ttk.Combobox(row3, textvariable=ws_return_var, values=["igen","nem"], width=7)
        ws_return_combo.pack(side=tk.LEFT)

        # Szemle a vásárló otthonában
        inspection_frame = ttk.LabelFrame(scrollable_frame, text="Szemle a vásárló otthonában", padding=10)
        inspection_frame.pack(fill=tk.X, padx=10, pady=10)
        
        insp_cust = comp_data.get("inspection_at_customer", {})
        
        row1 = ttk.Frame(inspection_frame)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="Szemle tervezett időpont (YYYY-MM-DD):", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        sched_var = tk.StringVar(value=insp_cust.get("scheduled") or "")
        sched_entry = tk.Entry(row1, textvariable=sched_var, width=15,
                              bg="#4B4B4B", fg="white", insertbackground="white")
        sched_entry.pack(side=tk.LEFT)
        
        row2 = ttk.Frame(inspection_frame)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="Szemle megtörtént?", style='Bold.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        done_var = tk.StringVar(value="igen" if insp_cust.get("done") else "nem")
        done_combo = ttk.Combobox(row2, textvariable=done_var, values=["igen","nem"], width=7)
        done_combo.pack(side=tk.LEFT)

        # Fájl lista keret
        files_frame = ttk.LabelFrame(scrollable_frame, text="Csatolt Fájlok", padding=10)
        files_frame.pack(fill=tk.X, padx=10, pady=10)

        files_container = ttk.Frame(files_frame)
        files_container.pack(fill=tk.BOTH, expand=True)
        
        # Listbox és scrollbar
        list_frame = ttk.Frame(files_container)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        photos_list = comp_data.get("photos", [])
        self.files_listbox = tk.Listbox(list_frame, height=6, bg="#4B4B4B", fg="white", 
                                        selectbackground="#306998", font=("Arial", 9))
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.files_listbox.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_listbox.config(yscrollcommand=scroll_y.set)

        for f in photos_list:
            self.files_listbox.insert(tk.END, f)
        
        # Fájl művelet gombok
        button_frame = ttk.Frame(files_container)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        def open_selected_file():
            sel = self.files_listbox.curselection()
            if not sel:
                messagebox.showwarning("Nincs kijelölve", "Kérlek jelölj ki egy fájlt a listából.")
                return
            file_name = self.files_listbox.get(sel[0])
            local_path = os.path.join(PHOTOS_DIR, file_name)
            if not os.path.exists(local_path):
                messagebox.showerror("Hiba", f"A fájl nem található: {local_path}")
                return
            try:
                subprocess.run(["open", local_path])  # Mac
            except Exception as e:
                messagebox.showerror("Hiba", f"Nem sikerült megnyitni a fájlt: {e}")

        def export_selected_file():
            sel = self.files_listbox.curselection()
            if not sel:
                messagebox.showwarning("Nincs kijelölve", "Kérlek jelölj ki egy fájlt a listából.")
                return
            file_name = self.files_listbox.get(sel[0])
            local_path = os.path.join(PHOTOS_DIR, file_name)
            if not os.path.exists(local_path):
                messagebox.showerror("Hiba", f"A fájl nem található: {local_path}")
                return
            save_path = filedialog.asksaveasfilename(
                title="Fájl mentése",
                initialfile=file_name,
                defaultextension=os.path.splitext(file_name)[1]
            )
            if not save_path:
                return
            try:
                shutil.copy2(local_path, save_path)
                messagebox.showinfo("Siker", f"A fájlt elmentettük ide:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Hiba", f"Fájl mentési hiba: {e}")

        def delete_selected_file():
            sel = self.files_listbox.curselection()
            if not sel:
                messagebox.showwarning("Nincs kijelölve", "Kérlek jelölj ki egy fájlt, amit törölni szeretnél.")
                return
            file_name = self.files_listbox.get(sel[0])
            local_path = os.path.join(PHOTOS_DIR, file_name)
            confirm = messagebox.askyesno("Megerősítés", f"Biztosan törlöd ezt a fájlt?\n{file_name}")
            if confirm:
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except:
                        pass
                comp_data["photos"].remove(file_name)
                self.data_manager.save_complaints()
                self.files_listbox.delete(sel[0])
                messagebox.showinfo("Siker", f"{file_name} törölve.")

        ttk.Button(button_frame, text="Megnyitás", command=open_selected_file).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Letöltés", command=export_selected_file).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Törlés", command=delete_selected_file).pack(fill=tk.X, pady=2)

        # Mentés gomb – itt olvassuk ki MINDEN combobox/entry értékét
        def save_changes():
            # Alapmezők
            comp_data["customer"] = cust_var.get().strip()
            comp_data["customer_address"] = address_var.get().strip()
            comp_data["product_name"] = product_var.get().strip()
            comp_data["brand"] = brand_var.get().strip()
            comp_data["complaint_description"] = complaint_var.get().strip()
            comp_data["status"] = status_var.get().strip()
            comp_data["manufacturer_response"] = man_response_var.get().strip()

            comp_data["start_date"] = start_var.get().strip()
            comp_data["deadline_days"] = deadline_var.get().strip()
            comp_data["manufacturer_sent_date"] = man_sent_var.get().strip()
            comp_data["manufacturer_deadline_days"] = man_deadline_var.get().strip()

            # Ha Elitestrom, olvassuk ki az i_vars comboboxokat
            if is_elitestrom:
                if "inspection" not in comp_data:
                    comp_data["inspection"] = {
                        "szemle": False,
                        "műhelybe_hozva": False,
                        "megjavítva": False,
                        "vissza_vitt": False
                    }
                # i_vars-ban van: (var, key)
                for (var, key) in i_vars:
                    comp_data["inspection"][key] = (var.get() == "igen")

                # Ha volt esetleg import_info, töröljük
                if "import_info" in comp_data:
                    del comp_data["import_info"]

            else:
                # Nem Elitestrom -> import_info mezőket kell kiolvasni
                if "import_info" not in comp_data:
                    comp_data["import_info"] = {
                        "szamlaszam": None,
                        "datum": None,
                        "iroda_feldolgozva": False
                    }

                comp_data["import_info"]["szamlaszam"] = inv_no_var.get().strip()
                comp_data["import_info"]["datum"] = inv_date_var.get().strip()
                comp_data["import_info"]["iroda_feldolgozva"] = (office_var.get() == "igen")

                # Ha volt "inspection" mező, töröljük
                if "inspection" in comp_data:
                    del comp_data["inspection"]

            # Műhelyes mezők
            ws = comp_data.get("workshop_status", {})
            ws["in_workshop"] = (ws_in_var.get() == "igen")
            ws["repair_done"] = (ws_repair_var.get() == "igen")
            ws["returned_to_customer"] = (ws_return_var.get() == "igen")
            comp_data["workshop_status"] = ws

            # Otthoni szemle
            iac = comp_data.get("inspection_at_customer", {})
            iac["scheduled"] = sched_var.get().strip() or None
            iac["done"] = (done_var.get() == "igen")
            comp_data["inspection_at_customer"] = iac

            # Végső mentés
            self.data_manager.save_complaints()
            messagebox.showinfo("Siker", "Minden változás mentve.")
            self.refresh_tree()
            self.status_var.set(f"{comp_no} adatai mentve")
            win.destroy()

        # Gombsáv alul, nyúlik az ablak aljáig
        button_bar = tk.Frame(main_container, bg="#2B2B2B", height=50)
        button_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))
        
        save_button = ttk.Button(button_bar, text="Módosítások Mentése", command=save_changes, padding=(10, 5))
        save_button.pack(side=tk.RIGHT, padx=10)
        
        cancel_button = ttk.Button(button_bar, text="Mégse", command=win.destroy, padding=(10, 5))
        cancel_button.pack(side=tk.RIGHT, padx=10)
        
        # Esc billentyű kezelése
        win.bind("<Escape>", lambda event: win.destroy())
        
        # Ablak középre pozicionálása
        win.update_idletasks()
        width = win.winfo_width()
        height = win.winfo_height()
        x = (win.winfo_screenwidth() // 2) - (width // 2)
        y = (win.winfo_screenheight() // 2) - (height // 2)
        win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        

    # ----------------------------------------------------------------
    #                    FÁJL CSATOLÁSA
    # ----------------------------------------------------------------
    def add_media(self):
        comp_no = self.get_selected_complaint_number()
        if not comp_no:
            messagebox.showerror("Hiba", "Nincs kiválasztva reklamáció!")
            return

        if comp_no not in self.data_manager.complaints:
            messagebox.showerror("Hiba", "A kiválasztott reklamáció nem létezik.")
            return

        comp = self.data_manager.complaints[comp_no]
        if comp.get("status", "open") == "closed":
            messagebox.showwarning("Lezárt reklamáció", "Ez a reklamáció lezárva, nem adható hozzá új fájl.")
            return

        download_dir = os.path.expanduser("~/Downloads")
        file_path = filedialog.askopenfilename(
            title="Fájl kiválasztása",
            initialdir=download_dir,
            filetypes=[("Minden fájl", "*.*")]
        )
        if not file_path:
            return

        self.data_manager.ensure_photos_folder()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file_path)[1]
        new_filename = f"{comp_no}_{timestamp}{ext}"
        new_filepath = os.path.join(PHOTOS_DIR, new_filename)

        try:
            shutil.copy2(file_path, new_filepath)
            comp["photos"].append(new_filename)
            self.data_manager.save_complaints()
            messagebox.showinfo("Siker", f"Fájl hozzáadva: {new_filename}")
            self.refresh_tree()
            self.status_var.set(f"Új fájl csatolva: {new_filename}")
        except Exception as e:
            messagebox.showerror("Hiba", f"Fájl másolási hiba: {e}")

    # ----------------------------------------------------------------
    #                  REKLAMÁCIÓ LEZÁRÁSA
    # ----------------------------------------------------------------
    def close_complaint(self):
        comp_no = self.get_selected_complaint_number()
        if not comp_no:
            messagebox.showerror("Hiba", "Nincs kiválasztva reklamáció!")
            return

        comp = self.data_manager.complaints.get(comp_no, None)
        if not comp:
            messagebox.showerror("Hiba", "A kiválasztott reklamáció nem létezik.")
            return

        if comp.get("status", "open") == "closed":
            messagebox.showinfo("Figyelem", "Ez a reklamáció már lezárva.")
            return

        confirm = messagebox.askyesno("Megerősítés", f"Biztosan lezárja a(z) {comp_no} reklamációt?")
        if confirm:
            comp["status"] = "closed"
            self.data_manager.save_complaints()
            messagebox.showinfo("Siker", "Reklamáció lezárva.")
            self.refresh_tree()
            self.status_var.set(f"Reklamáció lezárva: {comp_no}")

    # ----------------------------------------------------------------
    #             BEADVÁNY (SZÖVEGES, HTML)
    # ----------------------------------------------------------------
    def generate_text_submission(self):
        comp_no = self.get_selected_complaint_number()
        if not comp_no:
            messagebox.showerror("Hiba", "Nincs kiválasztva reklamáció!")
            return
        if comp_no not in self.data_manager.complaints:
            messagebox.showerror("Hiba", "A kiválasztott reklamáció nem létezik.")
            return

        comp = self.data_manager.complaints[comp_no]
        lines = []
        lines.append("=== Beadvány (Szöveges) ===")
        lines.append(f"Reklamáció száma: {comp_no}")
        lines.append(f"Vásárló neve: {comp.get('customer','')}")
        lines.append(f"Lakcím: {comp.get('customer_address','')}")
        lines.append(f"Termék neve: {comp.get('product_name','')}")
        lines.append(f"Panasz: {comp.get('complaint_description','')}")
        lines.append(f"Márka: {comp.get('brand','')}")
        lines.append(f"Státusz: {comp.get('status','open')}")

        if comp.get("brand","").lower() == "elitestrom":
            lines.append("Ellenőrzési adatok (Elitestrom):")
            insp = comp.get("inspection", {})
            for k, v in insp.items():
                lines.append(f"  {k}: {'igen' if v else 'nem'}")
        else:
            imp = comp.get("import_info", {})
            lines.append("Import számla információ:")
            lines.append(f"  Számlaszám: {imp.get('szamlaszam','Nincs')}")
            lines.append(f"  Dátum: {imp.get('datum','Nincs')}")
            lines.append(f"  Iroda megküldte: {'igen' if imp.get('iroda_feldolgozva') else 'nem'}")

        photos = comp.get("photos", [])
        if photos:
            lines.append("Csatolt fájlok:")
            for p in photos:
                lines.append(f"  - {p}")
        else:
            lines.append("Csatolt fájlok: Nincsenek")

        manresp = comp.get("manufacturer_response","")
        lines.append(f"Gyártó válasza: {manresp if manresp else 'Nincs rögzítve'}")

        notes = comp.get("additional_info", [])
        if notes:
            lines.append("Utólagos megjegyzések:")
            for n in notes:
                lines.append(f"  - {n}")
        else:
            lines.append("Utólagos megjegyzések: Nincsenek")

        txt = "\n".join(lines)
        filename = f"{comp_no}_submission.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(txt)

        messagebox.showinfo("Beadvány", f"Szöveges beadvány generálva:\n{filename}")
        self.status_var.set(f"Szöveges beadvány generálva: {filename}")

    def generate_html_submission(self):
        comp_no = self.get_selected_complaint_number()
        if not comp_no:
            messagebox.showerror("Hiba", "Nincs kiválasztva reklamáció!")
            return
        if comp_no not in self.data_manager.complaints:
            messagebox.showerror("Hiba", "A kiválasztott reklamáció nem létezik.")
            return

        comp = self.data_manager.complaints[comp_no]
        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html lang='hu'><head><meta charset='utf-8'>")
        html.append("<title>Beadvány - {}</title>".format(comp_no))
        html.append("<style>")
        html.append("body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; }")
        html.append("h1, h2 { color: #306998; }")
        html.append("img { max-width: 100%; height: auto; margin: 10px 0; border: 1px solid #ddd; }")
        html.append(".info-section { margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }")
        html.append("</style>")
        html.append("</head><body>")
        html.append("<h1>Reklamáció Beadvány</h1>")
        
        html.append("<div class='info-section'>")
        html.append(f"<p><strong>Reklamáció száma:</strong> {comp_no}</p>")
        html.append(f"<p><strong>Vásárló neve:</strong> {comp.get('customer','')}</p>")
        html.append(f"<p><strong>Lakcím:</strong> {comp.get('customer_address','')}</p>")
        html.append(f"<p><strong>Termék neve:</strong> {comp.get('product_name','')}</p>")
        html.append(f"<p><strong>Panasz:</strong> {comp.get('complaint_description','')}</p>")
        html.append(f"<p><strong>Márka:</strong> {comp.get('brand','')}</p>")
        html.append(f"<p><strong>Státusz:</strong> {comp.get('status','open')}</p>")
        html.append("</div>")

        if comp.get("brand","").lower() == "elitestrom":
            html.append("<div class='info-section'>")
            html.append("<h2>Ellenőrzési adatok (Elitestrom)</h2><ul>")
            for k,v in comp.get("inspection", {}).items():
                html.append(f"<li>{k}: {'igen' if v else 'nem'}</li>")
            html.append("</ul></div>")
        else:
            imp = comp.get("import_info", {})
            html.append("<div class='info-section'>")
            html.append("<h2>Import számla információ</h2>")
            html.append(f"<p><strong>Számlaszám:</strong> {imp.get('szamlaszam','Nincs')}</p>")
            html.append(f"<p><strong>Dátum:</strong> {imp.get('datum','Nincs')}</p>")
            html.append(f"<p><strong>Iroda megküldte:</strong> {'igen' if imp.get('iroda_feldolgozva') else 'nem'}</p>")
            html.append("</div>")

        photos = comp.get("photos", [])
        if photos:
            html.append("<div class='info-section'>")
            html.append("<h2>Csatolt fájlok</h2>")
            for p in photos:
                photo_path = os.path.join(PHOTOS_DIR, p)
                html.append(f"<div><img src='{photo_path}' alt='Média' style='max-width:600px;'/></div>")
                html.append(f"<p><small>Fájl: {p}</small></p>")
            html.append("</div>")
        else:
            html.append("<div class='info-section'>")
            html.append("<p>Nincs feltöltött fájl</p>")
            html.append("</div>")

        manresp = comp.get("manufacturer_response","")
        html.append("<div class='info-section'>")
        if manresp:
            html.append(f"<p><strong>Gyártó válasza:</strong> {manresp}</p>")
        else:
            html.append("<p><strong>Gyártó válasza:</strong> Nincs rögzítve</p>")
        html.append("</div>")

        notes = comp.get("additional_info", [])
        if notes:
            html.append("<div class='info-section'>")
            html.append("<h2>Utólagos megjegyzések</h2><ul>")
            for n in notes:
                html.append(f"<li>{n}</li>")
            html.append("</ul></div>")
        else:
            html.append("<div class='info-section'>")
            html.append("<p>Nincsenek utólagos megjegyzések</p>")
            html.append("</div>")

        html.append("<div class='info-section' style='font-size: 0.8em; color: #666; text-align: center;'>")
        html.append(f"<p>Generálva: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>")
        html.append("</div>")
        
        html.append("</body></html>")
        html_content = "\n".join(html)
        filename = f"{comp_no}_submission.html"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            webbrowser.open_new_tab(os.path.abspath(filename))
            messagebox.showinfo("Beadvány", f"HTML beadvány generálva:\n{filename}")
            self.status_var.set(f"HTML beadvány generálva: {filename}")
        except Exception as e:
            messagebox.showerror("Hiba", f"Nem sikerült a HTML fájl írása: {e}")

    # ----------------------------------------------------------------
    #       DOKUMENTÁCIÓ GENERÁLÁSA (HATÁRIDŐK + WORKSHOP + SZEMLE)
    # ----------------------------------------------------------------
    def generate_documentation(self):
        comp_no = self.get_selected_complaint_number()
        if not comp_no:
            messagebox.showerror("Hiba", "Nincs kiválasztva reklamáció!")
            return
        if comp_no not in self.data_manager.complaints:
            messagebox.showerror("Hiba", "A kiválasztott reklamáció nem létezik.")
            return

        comp = self.data_manager.complaints[comp_no]
        doc_lines = []
        doc_lines.append("<!DOCTYPE html>")
        doc_lines.append("<html lang='hu'><head><meta charset='utf-8'>")
        doc_lines.append("<title>Dokumentáció - {}</title>".format(comp_no))
        doc_lines.append("<style>")
        doc_lines.append("body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; }")
        doc_lines.append("h1, h2 { color: #306998; }")
        doc_lines.append("table { width: 100%; border-collapse: collapse; margin: 15px 0; }")
        doc_lines.append("th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }")
        doc_lines.append("th { background-color: #306998; color: white; }")
        doc_lines.append("tr:nth-child(even) { background-color: #f2f2f2; }")
        doc_lines.append(".section { margin-bottom: 30px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }")
        doc_lines.append(".status-ok { color: green; }")
        doc_lines.append(".status-warning { color: orange; }")
        doc_lines.append(".status-danger { color: red; }")
        doc_lines.append("</style>")
        doc_lines.append("</head><body>")
        
        # Fejléc
        doc_lines.append("<div class='section'>")
        doc_lines.append("<h1>Reklamáció Részletes Dokumentáció</h1>")
        doc_lines.append("<table>")
        doc_lines.append("<tr><th colspan='2'>Alapadatok</th></tr>")
        doc_lines.append(f"<tr><td>Reklamáció száma:</td><td><strong>{comp_no}</strong></td></tr>")
        doc_lines.append(f"<tr><td>Vásárló neve:</td><td>{comp.get('customer','')}</td></tr>")
        doc_lines.append(f"<tr><td>Termék neve:</td><td>{comp.get('product_name','')}</td></tr>")
        doc_lines.append(f"<tr><td>Panasz:</td><td>{comp.get('complaint_description','')}</td></tr>")
        doc_lines.append(f"<tr><td>Márka:</td><td>{comp.get('brand','')}</td></tr>")
        
        status = comp.get('status','open')
        status_class = "status-ok" if status == "closed" else "status-warning"
        doc_lines.append(f"<tr><td>Státusz:</td><td class='{status_class}'>{status}</td></tr>")
        doc_lines.append("</table>")
        doc_lines.append("</div>")

        # Határidők szakasz
        doc_lines.append("<div class='section'>")
        doc_lines.append("<h2>Határidők</h2>")
        doc_lines.append("<table>")
        
        start_date = comp.get("start_date","N/A")
        deadline_days = comp.get("deadline_days","N/A")
        
        # Kiszámítjuk hátralévő napokat
        days_left = "N/A"
        status_class = ""
        try:
            if start_date != "N/A" and deadline_days != "N/A":
                start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
                today = datetime.date.today()
                days_passed = (today - start_dt).days
                days_left = int(deadline_days) - days_passed
                
                if days_left < 0:
                    status_class = "status-danger"
                elif days_left <= 5:
                    status_class = "status-warning"
                else:
                    status_class = "status-ok"
        except:
            pass
        
        doc_lines.append(f"<tr><td>(Saját) Ügyintézés kezdete:</td><td>{start_date}</td></tr>")
        doc_lines.append(f"<tr><td>(Saját) Határidő (napokban):</td><td>{deadline_days}</td></tr>")
        
        if days_left != "N/A":
            doc_lines.append(f"<tr><td>Hátralévő napok:</td><td class='{status_class}'>{days_left}</td></tr>")
        
        doc_lines.append("</table>")
        doc_lines.append("</div>")

        # Gyártói határidők
        doc_lines.append("<div class='section'>")
        doc_lines.append("<h2>Gyártói válasz határideje</h2>")
        doc_lines.append("<table>")
        
        man_sent = comp.get("manufacturer_sent_date","N/A")
        man_deadline = comp.get("manufacturer_deadline_days","N/A")
        
        # Gyártói hátralévő napok
        man_days_left = "N/A"
        man_status_class = ""
        try:
            if man_sent != "N/A" and man_deadline != "N/A":
                man_sent_dt = datetime.datetime.strptime(man_sent, "%Y-%m-%d").date()
                today = datetime.date.today()
                man_days_passed = (today - man_sent_dt).days
                man_days_left = int(man_deadline) - man_days_passed
                
                if man_days_left < 0:
                    man_status_class = "status-danger"
                elif man_days_left <= 3:
                    man_status_class = "status-warning"
                else:
                    man_status_class = "status-ok"
        except:
            pass
        
        doc_lines.append(f"<tr><td>Elküldve:</td><td>{man_sent}</td></tr>")
        doc_lines.append(f"<tr><td>Határidő (nap):</td><td>{man_deadline}</td></tr>")
        
        if man_days_left != "N/A":
            doc_lines.append(f"<tr><td>Hátralévő napok:</td><td class='{man_status_class}'>{man_days_left}</td></tr>")
        
        manresp = comp.get("manufacturer_response","")
        resp_status = "status-danger" if not manresp and man_days_left != "N/A" and man_days_left < 0 else ""
        
        if manresp:
            doc_lines.append(f"<tr><td>Gyártó válasz:</td><td>{manresp}</td></tr>")
        else:
            doc_lines.append(f"<tr><td>Gyártó válasz:</td><td class='{resp_status}'>Nincs rögzítve</td></tr>")
        
        doc_lines.append("</table>")
        doc_lines.append("</div>")

        # Műhely
        doc_lines.append("<div class='section'>")
        doc_lines.append("<h2>Műhelyes állapot</h2>")
        doc_lines.append("<table>")
        ws = comp.get("workshop_status", {})
        
        in_ws = "igen" if ws.get('in_workshop') else "nem"
        repaired = "igen" if ws.get('repair_done') else "nem"
        returned = "igen" if ws.get('returned_to_customer') else "nem"
        
        doc_lines.append(f"<tr><td>Behozva a műhelybe:</td><td>{in_ws}</td></tr>")
        doc_lines.append(f"<tr><td>Megjavítva:</td><td>{repaired}</td></tr>")
        doc_lines.append(f"<tr><td>Visszaszállítva a vevőhöz:</td><td>{returned}</td></tr>")
        doc_lines.append("</table>")
        doc_lines.append("</div>")

        # Szemle
        doc_lines.append("<div class='section'>")
        doc_lines.append("<h2>Szemle a vásárló otthonában</h2>")
        doc_lines.append("<table>")
        iac = comp.get("inspection_at_customer", {})
        
        scheduled = iac.get('scheduled','Nincs')
        done = "igen" if iac.get('done') else "nem"
        
        doc_lines.append(f"<tr><td>Tervezett időpont:</td><td>{scheduled}</td></tr>")
        doc_lines.append(f"<tr><td>Megtörtént:</td><td>{done}</td></tr>")
        doc_lines.append("</table>")
        doc_lines.append("</div>")
        
        # Lábléc
        doc_lines.append("<div style='font-size: 0.8em; color: #666; text-align: center; margin-top: 30px;'>")
        doc_lines.append(f"<p>Dokumentáció készült: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>")
        doc_lines.append("</div>")
        
        doc_lines.append("</body></html>")
        html_content = "\n".join(doc_lines)
        filename = f"{comp_no}_documentation.html"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            webbrowser.open_new_tab(os.path.abspath(filename))
            messagebox.showinfo("Dokumentáció", f"Részletes dokumentáció generálva:\n{filename}")
            self.status_var.set(f"Dokumentáció generálva: {filename}")
        except Exception as e:
            messagebox.showerror("Hiba", f"Nem sikerült a dokumentáció mentése: {e}")


# --------------------------------------------------------------------
#                            FŐ
# --------------------------------------------------------------------
if __name__ == "__main__":
    dm = DataManager(DATA_FILE)
    dm.ensure_photos_folder()
    app = ComplaintApp(dm)
    print("A program elindult, várakozás a Tkinter ablakra...")
    app.mainloop()
