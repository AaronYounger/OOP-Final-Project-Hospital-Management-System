# Calendar.py  ✅ UPDATED to:
# 1) Save appointments with the fields you want (PatientID, PatientName, DoctorName, AppointmentDate, DurationMinutes, ScheduledAt)
# 2) Still keep capacity logic working (Units + Status)
# 3) Call the GUI callback with BOTH (duration_minutes, the_date)

import os
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
import calendar as pycal

# ---------- Config ----------
MONTH = 12
YEAR = 2025
DURATION_TO_UNITS = {30: 1.0, 45: 1.5, 60: 2.0}

# Theme (centralized so you can tweak in one place)
THEME = {
    "window_bg": "#f1f1f1",
    "weekday_strip_bg": "#3a3a3a",
    "weekday_strip_fg": "white",
    "header_font": ("Segoe UI", 16, "bold"),
    "weekday_font": ("Segoe UI", 10, "bold"),
    "day_font": ("Segoe UI", 12, "bold"),
    "btn_available_bg": "white",
    "btn_unavailable_bg": "#e3e3e3",
    "btn_fg": "#222222",
    "btn_border": 2,
    "legend_border_relief": "groove",
}

# Data file names (relative to this file)
BASE_PATH = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_PATH, "data")
AVAIL_FILE = os.path.join(DATA_DIR, "Availability_December_2025.csv")
APPTS_FILE = os.path.join(DATA_DIR, "Appointments.csv")
DOCTORS_FILE = os.path.join(DATA_DIR, "Doctors.csv")  # used to map DoctorID -> Doctor Name


# ---------- Simplest possible tooltip ----------
class HoverTooltip:
    def __init__(self, widget, text_provider):
        self.widget = widget
        self.text_provider = text_provider  # function returning text
        self.tip = None
        widget.bind("<Enter>", self._on)
        widget.bind("<Leave>", self._off)

    def _on(self, event=None):
        text = self.text_provider()
        if not text:
            return
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw, text=text, justify="left",
            relief="solid", borderwidth=1, padx=6, pady=4,
            background="#ffffe0"
        )
        lbl.pack()

    def _off(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ---------- Data helpers ----------
def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_availability():
    _ensure_data_dir()
    if not os.path.exists(AVAIL_FILE):
        raise FileNotFoundError(f"Availability file not found at: {AVAIL_FILE}")
    df = pd.read_csv(AVAIL_FILE)

    expected = {"DoctorID", "Date", "IsAvailable", "DailyCapacityUnits", "Notes"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in availability CSV: {missing}")

    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    if df["IsAvailable"].dtype != bool:
        df["IsAvailable"] = df["IsAvailable"].astype(str).str.lower().isin(["true", "1", "yes"])

    return df

def load_appointments():
    """
    Creates/loads Appointments.csv.

    ✅ Required user fields:
      PatientID, PatientName, DoctorName, AppointmentDate, DurationMinutes, ScheduledAt

    ✅ Also keeps internal fields needed for capacity logic:
      DoctorID, Units, Status, AppointmentID
    """
    _ensure_data_dir()

    # New schema (works for both your needs + capacity logic)
    cols = [
        "AppointmentID",
        "DoctorID",
        "DoctorName",
        "AppointmentDate",
        "DurationMinutes",
        "Units",
        "PatientID",
        "PatientName",
        "Status",
        "ScheduledAt",
    ]

    if not os.path.exists(APPTS_FILE):
        pd.DataFrame(columns=cols).to_csv(APPTS_FILE, index=False)

    df = pd.read_csv(APPTS_FILE)

    # ---- Backward compatibility (if you already had older columns) ----
    # Old file used "Date" and "CreatedAt"
    if "AppointmentDate" not in df.columns and "Date" in df.columns:
        df = df.rename(columns={"Date": "AppointmentDate"})
    if "ScheduledAt" not in df.columns and "CreatedAt" in df.columns:
        df = df.rename(columns={"CreatedAt": "ScheduledAt"})

    # Ensure any missing expected columns exist
    for c in cols:
        if c not in df.columns:
            df[c] = ""

    # Parse AppointmentDate to datetime.date for comparisons
    if not df.empty:
        df["AppointmentDate"] = pd.to_datetime(df["AppointmentDate"], errors="coerce").dt.date

    return df[cols]

def save_appointments(df):
    # Save with dates as ISO strings so Excel reads them cleanly
    out = df.copy()
    if "AppointmentDate" in out.columns:
        out["AppointmentDate"] = out["AppointmentDate"].apply(lambda d: d.isoformat() if isinstance(d, date) else str(d))
    out.to_csv(APPTS_FILE, index=False)

def load_doctor_names():
    """
    Returns dict like {'D001': 'Dr. Daniel Blake', ...}
    Works whether the column is 'DoctorName' or 'Doctor Name'.
    """
    if not os.path.exists(DOCTORS_FILE):
        print(f"[Calendar] Doctors file not found at: {DOCTORS_FILE}")
        return {}

    df = pd.read_csv(DOCTORS_FILE)

    normalized_cols = {c.strip().lower().replace(" ", ""): c for c in df.columns}

    id_col = normalized_cols.get("doctorid") or normalized_cols.get("id")
    name_col = (
        normalized_cols.get("doctorname") or
        normalized_cols.get("doctor") or
        normalized_cols.get("name")
    )

    if not id_col or not name_col:
        print(f"[Calendar] Could not find DoctorID/DoctorName columns in Doctors.csv. Found: {list(df.columns)}")
        return {}

    mapping = dict(zip(df[id_col].astype(str), df[name_col].astype(str)))
    print(f"[Calendar] Loaded {len(mapping)} doctor names from Doctors.csv")
    return mapping


# ---------- App Core ----------
class CalendarApp(tk.Toplevel):
    """
    UPDATED:
    - Accepts an on_confirm callback from the main GUI.
    - When a booking is successful, calls on_confirm(duration_minutes, the_date).
    """
    def __init__(self, master=None, doctor=None, patient=None, on_confirm=None):
        super().__init__(master)
        self.title("Schedule Appointment")
        self.geometry("820x640")
        self.resizable(False, False)
        self.configure(bg=THEME["window_bg"])

        # ✅ callback to send appointment length + date back to main app
        self.on_confirm = on_confirm

        # --------- Data state ---------
        self.availability_df = load_availability()
        self.appts_df = load_appointments()
        self.doctor_names = load_doctor_names()

        self.selected_doctor_id = None
        self.selected_patient_id = None
        self.doctor_display_name = None

        # --- Patient context ---
        if patient is not None:
            self.selected_patient_id = getattr(patient, "Pid", None)
            self.patient_name = getattr(patient, "Pname", "")  # ✅ NEW (name for CSV)
        else:
            self.patient_name = ""

        # --- Doctor context ---
        if doctor is not None:
            self.doctor_display_name = doctor.get("Name")  # what GUI shows

            doc_id = doctor.get("DoctorID")
            if doc_id:
                self.selected_doctor_id = str(doc_id)
            else:
                # fallback: match by name in Doctors.csv
                name_from_gui = doctor.get("Name")
                if name_from_gui and self.doctor_names:
                    for did, dname in self.doctor_names.items():
                        if dname == name_from_gui:
                            self.selected_doctor_id = str(did)
                            break

        # --------- Build UI ---------
        self.day_buttons = []
        self.status_var = tk.StringVar(value="Select a date to book.")
        self.month_name = pycal.month_name[MONTH]

        self._build_ui()

        if self.selected_doctor_id:
            self.set_context(
                doctor_id=self.selected_doctor_id,
                patient_id=self.selected_patient_id
            )
        else:
            self.status_var.set("No DoctorID set. (Doctor name may not match Doctors.csv.)")

    # ---- Wiring hooks for previous screen ----
    def set_context(self, doctor_id: str, patient_id: str | None = None):
        self.selected_doctor_id = doctor_id
        self.selected_patient_id = patient_id

        display_name = self.doctor_display_name
        if not display_name:
            display_name = self.doctor_names.get(str(doctor_id), str(doctor_id))

        self.header_label.config(text=f"{self.month_name} {YEAR} — {display_name}")
        self._render_month()

    # ---- UI build ----
    def _build_ui(self):
        header = tk.Frame(self, pady=8, bg=THEME["window_bg"])
        header.pack(fill="x")
        self.header_label = tk.Label(
            header,
            text=f"{self.month_name} {YEAR}",
            font=THEME["header_font"],
            bg=THEME["window_bg"]
        )
        self.header_label.pack(side="left", padx=12)

        legend = tk.Frame(self, pady=4, bg=THEME["window_bg"])
        legend.pack(fill="x")
        tk.Label(legend, text="Legend:", bg=THEME["window_bg"]).pack(side="left", padx=(12, 6))
        tk.Label(legend, text="Available", relief=THEME["legend_border_relief"], width=10,
                 bg=THEME["btn_available_bg"]).pack(side="left", padx=4)
        tk.Label(legend, text="Unavailable", relief=THEME["legend_border_relief"], width=10,
                 bg=THEME["btn_unavailable_bg"]).pack(side="left", padx=4)

        outer = tk.Frame(self, padx=12, pady=8, bg=THEME["window_bg"])
        outer.pack(fill="both", expand=True)

        strip = tk.Frame(outer, bg=THEME["weekday_strip_bg"], padx=6, pady=6)
        strip.grid(row=0, column=0, sticky="ew")
        for col in range(7):
            strip.grid_columnconfigure(col, weight=1)

        for col, wd in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            tk.Label(
                strip, text=wd, font=THEME["weekday_font"],
                bg=THEME["weekday_strip_bg"], fg=THEME["weekday_strip_fg"],
                padx=8, pady=2
            ).grid(row=0, column=col, padx=2, pady=0, sticky="ew")

        grid = tk.Frame(outer, padx=0, pady=8, bg=THEME["window_bg"])
        grid.grid(row=1, column=0, sticky="nsew")

        self.day_buttons.clear()
        for r in range(1, 7):
            row_buttons = []
            for c in range(7):
                btn = tk.Button(
                    grid, text="", width=6, height=2,
                    font=THEME["day_font"], fg=THEME["btn_fg"],
                    relief="raised", bd=THEME["btn_border"],
                    bg=THEME["btn_available_bg"], activebackground="#d9edf7",
                    highlightthickness=0, state="disabled",
                )
                btn.grid(row=r, column=c, padx=6, pady=6)
                row_buttons.append(btn)
            self.day_buttons.append(row_buttons)

        footer = tk.Frame(self, pady=6, bg=THEME["window_bg"])
        footer.pack(fill="x")
        tk.Label(footer, textvariable=self.status_var, anchor="w",
                 bg=THEME["window_bg"]).pack(side="left", padx=12)

    # ---- Month render ----
    def _render_month(self):
        if not self.selected_doctor_id:
            self.status_var.set("No DoctorID set. (Call set_context(doctor_id) from previous screen.)")
            return

        first_weekday, num_days = pycal.monthrange(YEAR, MONTH)  # Mon=0..Sun=6
        today = date.today()

        for r in range(6):
            for c in range(7):
                btn = self.day_buttons[r][c]
                btn.config(
                    text="",
                    state="disabled",
                    bg=THEME["btn_available_bg"],
                    relief="raised",
                    bd=THEME["btn_border"]
                )
                HoverTooltip(btn, lambda: "")

        current_row = 0
        current_col = first_weekday
        for day in range(1, num_days + 1):
            btn = self.day_buttons[current_row][current_col]
            the_date = date(YEAR, MONTH, day)
            btn.config(text=str(day))

            info = self._get_day_info(self.selected_doctor_id, the_date)
            tooltip_text = info["tooltip"]
            clickable = info["clickable"]

            if clickable:
                btn.config(state="normal", bg=THEME["btn_available_bg"])
            else:
                btn.config(state="disabled", bg=THEME["btn_unavailable_bg"])

            if the_date == today:
                btn.config(relief="solid", bd=THEME["btn_border"] + 1)

            btn.config(command=lambda d=the_date: self._choose_duration(d))
            HoverTooltip(btn, lambda t=tooltip_text: t)

            current_col += 1
            if current_col > 6:
                current_col = 0
                current_row += 1

        display_name = self.doctor_names.get(str(self.selected_doctor_id), str(self.selected_doctor_id))
        self.status_var.set(f"Showing {self.month_name} {YEAR} for {display_name}")

    def _get_day_info(self, doctor_id, the_date: date):
        rows = self.availability_df[
            (self.availability_df["DoctorID"].astype(str) == str(doctor_id)) &
            (self.availability_df["Date"] == the_date)
        ]

        if rows.empty:
            return {"clickable": False, "tooltip": "Unavailable: No data"}

        row = rows.iloc[0]
        is_available = bool(row["IsAvailable"])
        daily_units = int(row["DailyCapacityUnits"])
        notes = str(row.get("Notes", "")) if not pd.isna(row.get("Notes", "")) else ""

        remaining_units = self._get_remaining_units(doctor_id, the_date, daily_units)

        if not is_available:
            return {"clickable": False, "tooltip": f"Unavailable: {notes or 'Not a clinic day'}"}
        if remaining_units <= 0:
            return {"clickable": False, "tooltip": "Unavailable: Fully booked"}

        return {
            "clickable": True,
            "tooltip": f"Available: {remaining_units:g} units left" + (f" — {notes}" if notes else "")
        }

    def _get_remaining_units(self, doctor_id, the_date: date, daily_units: int) -> float:
        # capacity is based on "Units" of BOOKED appointments on same date
        same_day = self.appts_df[
            (self.appts_df["DoctorID"].astype(str) == str(doctor_id)) &
            (self.appts_df["AppointmentDate"] == the_date) &
            (self.appts_df["Status"].astype(str).str.lower() == "booked")
        ]
        used = same_day["Units"].sum() if not same_day.empty else 0.0
        remaining = daily_units - float(used)
        return max(0.0, round(remaining, 2))

    # ---- Booking flow ----
    def _choose_duration(self, the_date: date):
        dlg = tk.Toplevel(self)
        dlg.title(f"Choose duration — {the_date.isoformat()}")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text=f"Book appointment on {the_date.isoformat()}").pack(padx=12, pady=(12, 6))
        tk.Label(dlg, text="Select duration (minutes):").pack(padx=12, pady=(0, 6))

        duration_var = tk.StringVar(value="30")
        cmb = ttk.Combobox(dlg, textvariable=duration_var, values=["30", "45", "60"], state="readonly", width=10)
        cmb.pack(padx=12, pady=6)

        btns = tk.Frame(dlg)
        btns.pack(pady=(8, 12))
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=6)
        ttk.Button(btns, text="Book", command=lambda: self._try_book(dlg, the_date, int(duration_var.get()))).pack(side="right")

    def _try_book(self, dialog, the_date: date, duration_minutes: int):
        dialog.destroy()

        if not self.selected_doctor_id:
            messagebox.showwarning("Missing Doctor", "No DoctorID set. Cannot book.")
            return

        rows = self.availability_df[
            (self.availability_df["DoctorID"].astype(str) == str(self.selected_doctor_id)) &
            (self.availability_df["Date"] == the_date)
        ]
        if rows.empty:
            messagebox.showerror("Unavailable", "No availability data for this date.")
            return

        row = rows.iloc[0]
        if not bool(row["IsAvailable"]):
            messagebox.showerror("Unavailable", "This date is marked unavailable.")
            return

        units_needed = DURATION_TO_UNITS.get(duration_minutes)
        if units_needed is None:
            messagebox.showerror("Invalid duration", "Please choose 30, 45, or 60 minutes.")
            return

        daily_units = int(row["DailyCapacityUnits"])
        remaining = self._get_remaining_units(self.selected_doctor_id, the_date, daily_units)
        if remaining < units_needed:
            messagebox.showinfo("Fully booked", "Not enough capacity left for that duration.")
            return

        # ✅ Doctor name to store in CSV
        doctor_name = (
            self.doctor_display_name
            or self.doctor_names.get(str(self.selected_doctor_id), str(self.selected_doctor_id))
        )

        # ✅ New appointment row (has your required fields + capacity fields)
        appt_id = f"A-{int(datetime.now().timestamp())}"
        new_row = {
            "AppointmentID": appt_id,
            "DoctorID": str(self.selected_doctor_id),
            "DoctorName": doctor_name,
            "AppointmentDate": the_date,  # keep as date in memory; save_appointments will isoformat it
            "DurationMinutes": duration_minutes,
            "Units": units_needed,
            "PatientID": self.selected_patient_id if self.selected_patient_id else "",
            "PatientName": self.patient_name or "",
            "Status": "Booked",
            "ScheduledAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.appts_df = pd.concat([self.appts_df, pd.DataFrame([new_row])], ignore_index=True)

        # Ensure AppointmentDate is date type in memory (for comparisons)
        self.appts_df["AppointmentDate"] = pd.to_datetime(self.appts_df["AppointmentDate"], errors="coerce").dt.date

        save_appointments(self.appts_df)

        # ✅ send minutes + date back to main GUI (gui_hospital.py)
        if callable(self.on_confirm):
            try:
                self.on_confirm(duration_minutes, the_date)  # ✅ IMPORTANT
            except Exception as e:
                print(f"[Calendar] on_confirm callback failed: {e}")

        messagebox.showinfo("Booked", f"Appointment booked on {the_date.isoformat()} ({duration_minutes} min).")
        self._render_month()


# ---------- Public entry point ----------
def launch_calendar(doctor_id: str, patient_id: str | None = None):
    root = tk.Tk()
    root.withdraw()
    app = CalendarApp(master=root)
    app.set_context(doctor_id=doctor_id, patient_id=patient_id)
    app.mainloop()


# ---------- Standalone demo ----------
if __name__ == "__main__":
    launch_calendar("D002")
