# gui_hospital.py

import tkinter as tk
from tkinter import ttk, messagebox
import csv

# ✅ NEW imports for Billing.csv write
import os
from datetime import datetime

# 🔴 Make sure this matches your backend filename
from Patients_Code import Patient, Symptoms, Doctors, LoginSystem
from Calendar import CalendarApp


# =========================
# INPUT FORMATTING HELPERS
# =========================
def digits_only(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def format_with_pattern(digits: str, groups, sep="-", max_len=None):
    """
    groups: list like [3,3,4] for phone or [2,2,4] for DOB digits.
    """
    d = digits if max_len is None else digits[:max_len]
    parts = []
    i = 0
    for g in groups:
        if i >= len(d):
            break
        parts.append(d[i:i + g])
        i += g
    return sep.join(parts)

def attach_live_formatter(entry: tk.Entry, groups, max_digits, sep="-"):
    """
    Auto-formats an Entry while typing.
    Example: phone groups=[3,3,4], max_digits=10 -> XXX-XXX-XXXX
    """
    def on_key_release(_event=None):
        d = digits_only(entry.get())[:max_digits]
        entry.delete(0, tk.END)
        entry.insert(0, format_with_pattern(d, groups, sep=sep, max_len=max_digits))
    entry.bind("<KeyRelease>", on_key_release)


# =========================
# BILLING CSV LOADERS
# =========================
def load_insurance_discount_map(csv_path="Insurance_Companies.csv"):
    """
    Expects columns:
      InsuranceID, Insurance Company Name, DiscountPercent
    DiscountPercent is like 60 for 60% off.
    """
    m = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ins_id = str(row.get("InsuranceID", "")).strip()
            disc = row.get("DiscountPercent", "0")
            try:
                m[ins_id] = float(disc)
            except:
                m[ins_id] = 0.0
    return m

def load_doctor_fee_map(csv_path="Doctor_Fees.csv"):
    """
    Expects columns:
      Specialty, BaseFee

    NOTE:
    We normalize keys to lowercase+strip so matching is robust.
    """
    m = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            spec = (row.get("Specialty", "") or "").strip().lower()
            fee = row.get("BaseFee", "0")
            try:
                m[spec] = float(fee)
            except:
                m[spec] = 0.0
    return m


# =========================
# ✅ BILLING CSV WRITER (SAVE ONCE BUTTON)
# =========================
def append_billing_record(
    patient_id,
    patient_name,
    doctor_name,
    appt_date_iso,
    billing_cost,
    csv_path="Billing.csv"
):
    """
    Writes ONE billing record to Billing.csv (appends).
    Fields:
      PatientID, PatientName, DoctorName, AppointmentDate, BillingCost, BilledAt
    """
    file_exists = os.path.exists(csv_path)
    fieldnames = ["PatientID", "PatientName", "DoctorName", "AppointmentDate", "BillingCost", "BilledAt"]

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "PatientID": patient_id or "",
            "PatientName": patient_name or "",
            "DoctorName": doctor_name or "",
            "AppointmentDate": appt_date_iso or "",
            "BillingCost": f"{billing_cost:.2f}",
            "BilledAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


# =========================
# MAIN APP CONTROLLER
# =========================
class HospitalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hospital Management System")
        self.root.geometry("900x700")  # a bit bigger for symptoms/doctor lists

        # Backend objects
        self.login_system = LoginSystem("Patients.csv")
        self.patient = Patient()

        # These will be used later in flow
        self.symptom_obj = None          # Symptoms instance
        self.doctor_obj = Doctors("Doctor_Specializations_Unique.csv")
        self.category_doctor_map = Doctors.load_category_specialty_map(
            "Category_Specialty_Map.csv"
        )
        self.last_symptom_obj = None     # to go "back" to doctor list

        # ✅ store appointment length + date selected in Calendar
        self.last_appointment_minutes = None
        self.last_appointment_date = None  # ✅ NEW

        # Currently visible frame
        self.current_frame = None

        # Start on the login screen
        self.show_login_screen()

    # ✅ Calendar callback: CalendarApp calls this after booking
    # IMPORTANT: Calendar.py must call on_confirm(duration_minutes, the_date)
    def on_appointment_confirmed(self, minutes: int, appt_date):
        self.last_appointment_minutes = minutes
        self.last_appointment_date = appt_date
        print(f"[GUI] Appointment stored: {appt_date} for {minutes} minutes")

    # Generic helper to switch between screens
    def switch_frame(self, frame_class, *args, **kwargs):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame_class(self.root, self, *args, **kwargs)
        self.current_frame.pack(fill="both", expand=True)

    def show_login_screen(self):
        self.switch_frame(LoginScreen)

    def show_patient_info_screen(self):
        self.switch_frame(PatientInfoScreen)

    def show_options_screen(self):
        self.switch_frame(OptionsScreen)

    # --- Diagnostics flow: symptoms → doctors → details → calendar ---
    def show_symptoms_screen(self):
        self.symptom_obj = Symptoms("ICD10_Symptom_Categories.csv")
        self.switch_frame(SymptomsScreen, self.symptom_obj)

    def show_diagnostics_screen(self):
        self.show_symptoms_screen()

    def show_doctor_recommendations(self, symptom_obj):
        self.last_symptom_obj = symptom_obj
        self.switch_frame(DoctorRecommendationScreen, symptom_obj)

    def show_doctor_details_screen(self, doctor_info):
        self.switch_frame(DoctorDetailsScreen, doctor_info)

    def show_calendar_screen(self, doctor_info):
        """
        Open the Calendar GUI for the selected doctor, linked to the current patient.
        """
        if not self.patient.Pid:
            messagebox.showwarning(
                "No Patient",
                "Please make sure a patient is logged in before scheduling."
            )
            return

        # ✅ pass callback so calendar can store appointment length + date
        cal_win = CalendarApp(
            master=self.root,
            doctor=doctor_info,
            patient=self.patient,
            on_confirm=self.on_appointment_confirmed
        )

        cal_win.transient(self.root)
        cal_win.grab_set()

    def show_billing_screen(self, doctor_info):
        # ✅ require booking first so we have appointment length + date stored
        if self.last_appointment_minutes not in (30, 45, 60) or self.last_appointment_date is None:
            messagebox.showwarning(
                "No Appointment Saved",
                "Please schedule an appointment first so the system knows the appointment date and length."
            )
            return
        self.switch_frame(BillingScreen, doctor_info)

    def exit_app(self):
        """Closes the entire GUI cleanly."""
        if messagebox.askyesno("Exit", "Are you sure you want to sign out and close the program?"):
            self.root.destroy()


# =========================
# LOGIN SCREEN
# =========================
class LoginScreen(tk.Frame):
    def __init__(self, parent, app: HospitalApp):
        super().__init__(parent)
        self.app = app

        title = tk.Label(self, text="Patient Login / Registration",
                         font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(20, 10))

        tk.Label(self, text="Full Name:", font=("Segoe UI", 12)).grid(
            row=1, column=0, sticky="e", padx=10, pady=5
        )
        self.name_entry = tk.Entry(self, width=30)
        self.name_entry.grid(row=1, column=1, sticky="w", pady=5)

        tk.Label(self, text="Email:", font=("Segoe UI", 12)).grid(
            row=2, column=0, sticky="e", padx=10, pady=5
        )
        self.email_entry = tk.Entry(self, width=30)
        self.email_entry.grid(row=2, column=1, sticky="w", pady=5)

        tk.Label(self, text="Phone (XXX-XXX-XXXX):", font=("Segoe UI", 12)).grid(
            row=3, column=0, sticky="e", padx=10, pady=5
        )
        self.phone_entry = tk.Entry(self, width=30)
        self.phone_entry.grid(row=3, column=1, sticky="w", pady=5)

        attach_live_formatter(self.phone_entry, groups=[3, 3, 4], max_digits=10, sep="-")

        self.status_var = tk.StringVar()
        status_label = tk.Label(self, textvariable=self.status_var,
                                font=("Segoe UI", 11), fg="blue")
        status_label.grid(row=4, column=0, columnspan=2, pady=(10, 5))

        login_btn = tk.Button(
            self, text="Submit",
            command=self.on_submit_clicked,
            width=15, height=2
        )
        login_btn.grid(row=5, column=0, pady=20)

        next_btn = tk.Button(
            self, text="Next",
            command=self.on_next_clicked,
            width=15, height=2
        )
        next_btn.grid(row=5, column=1, pady=20)

    def on_submit_clicked(self):
        name = self.name_entry.get().strip()
        email = self.email_entry.get().strip()
        phone = self.phone_entry.get().strip()

        if not name:
            messagebox.showerror("Error", "Name cannot be empty.")
            return

        if not Patient.validate_email_format(email):
            messagebox.showerror("Error", "Email format is invalid.")
            return

        if not Patient.validate_phone_format(phone):
            messagebox.showerror("Error", "Phone format must be XXX-XXX-XXXX.")
            return

        pid, name, email, phone, is_new = self.app.login_system.authenticate_values(
            name, email, phone
        )

        self.app.patient.Pid = pid
        self.app.patient.Pname = name
        self.app.patient.email = email
        self.app.patient.Pnumber = phone

        if is_new:
            self.status_var.set(f"New patient registered! {pid}")
        else:
            self.status_var.set(f"Welcome back, {name}! ({pid})")

    def on_next_clicked(self):
        if not self.app.patient.Pid:
            messagebox.showwarning("Warning", "Please submit login info first.")
            return
        self.app.show_patient_info_screen()


# =========================
# PATIENT INFO SCREEN
# =========================
class PatientInfoScreen(tk.Frame):
    def __init__(self, parent, app: HospitalApp):
        super().__init__(parent)
        self.app = app

        self.allergies_list = list(self.app.patient.allergies)
        self.insurance_list = Patient.load_insurance_list("Insurance_Companies.csv")
        self.insurance_names = [
            item["Insurance Company Name"] for item in self.insurance_list
        ]

        title = tk.Label(self, text="Patient Information",
                         font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=(20, 10))

        tk.Label(self, text="Date of Birth (MM-DD-YYYY):", font=("Segoe UI", 12)).grid(
            row=1, column=0, sticky="e", padx=10, pady=5
        )
        self.dob_entry = tk.Entry(self, width=25)
        self.dob_entry.grid(row=1, column=1, sticky="w", pady=5)
        self.dob_entry.insert(0, self.app.patient.dob)
        attach_live_formatter(self.dob_entry, groups=[2, 2, 4], max_digits=8, sep="-")

        tk.Label(self, text="Gender:", font=("Segoe UI", 12)).grid(
            row=2, column=0, sticky="e", padx=10, pady=5
        )
        gender_options = ["Male", "Female", "Other"]

        self.gender_var = tk.StringVar(value=self.app.patient.gender or "")
        self.gender_dropdown = ttk.Combobox(
            self,
            textvariable=self.gender_var,
            values=gender_options,
            state="readonly",
            width=22
        )
        self.gender_dropdown.grid(row=2, column=1, sticky="w", pady=5)

        tk.Label(self, text="Address:", font=("Segoe UI", 12)).grid(
            row=3, column=0, sticky="e", padx=10, pady=5
        )
        self.address_entry = tk.Entry(self, width=40)
        self.address_entry.grid(row=3, column=1, sticky="w", pady=5)
        self.address_entry.insert(0, self.app.patient.Address)

        tk.Label(self, text="Zip Code:", font=("Segoe UI", 12)).grid(
            row=4, column=0, sticky="e", padx=10, pady=5
        )
        self.zip_entry = tk.Entry(self, width=15)
        self.zip_entry.grid(row=4, column=1, sticky="w", pady=5)
        self.zip_entry.insert(0, self.app.patient.zipcode)

        tk.Label(self, text="Social Security Number:", font=("Segoe UI", 12)).grid(
            row=5, column=0, sticky="e", padx=10, pady=5
        )
        self.ssn_entry = tk.Entry(self, width=20, show="*")
        self.ssn_entry.grid(row=5, column=1, sticky="w", pady=5)
        self.ssn_entry.insert(0, self.app.patient.ssn)
        attach_live_formatter(self.ssn_entry, groups=[3, 2, 4], max_digits=9, sep="-")

        self.show_ssn_var = tk.BooleanVar()
        show_check = tk.Checkbutton(
            self,
            text="Show SSN",
            variable=self.show_ssn_var,
            command=self.toggle_ssn
        )
        show_check.grid(row=5, column=2, padx=5)

        tk.Label(self, text="Allergies:", font=("Segoe UI", 12, "bold")).grid(
            row=6, column=0, sticky="ne", padx=10, pady=(15, 5)
        )
        self.allergy_entry = tk.Entry(self, width=25)
        self.allergy_entry.grid(row=6, column=1, sticky="w", pady=(15, 5))

        add_allergy_btn = tk.Button(
            self, text="Add Allergy",
            command=self.add_allergy
        )
        add_allergy_btn.grid(row=6, column=2, sticky="w", padx=5, pady=(15, 5))

        self.allergy_listbox = tk.Listbox(self, height=5, width=40)
        self.allergy_listbox.grid(row=7, column=1, columnspan=2, sticky="w", pady=5)

        for a in self.allergies_list:
            self.allergy_listbox.insert(tk.END, a)

        remove_allergy_btn = tk.Button(
            self, text="Remove Allergy",
            command=self.remove_allergy
        )
        remove_allergy_btn.grid(row=6, column=3, sticky="w", padx=5, pady=(15, 5))

        tk.Label(self, text="Insurance Company:", font=("Segoe UI", 12, "bold")).grid(
            row=8, column=0, sticky="e", padx=10, pady=(15, 5)
        )

        self.insurance_var = tk.StringVar()
        self.insurance_dropdown = ttk.Combobox(
            self,
            textvariable=self.insurance_var,
            values=self.insurance_names,
            state="readonly",
            width=25
        )
        self.insurance_dropdown.grid(row=8, column=1, sticky="w", pady=(15, 5))

        self.preselect_insurance()

        self.status_var = tk.StringVar()
        status_label = tk.Label(self, textvariable=self.status_var,
                                font=("Segoe UI", 11), fg="blue")
        status_label.grid(row=9, column=0, columnspan=3, pady=(10, 5))

        save_btn = tk.Button(
            self, text="Save Patient Info",
            command=self.save_patient_info,
            width=18, height=2
        )
        save_btn.grid(row=10, column=0, pady=20)

        next_btn = tk.Button(
            self, text="Next (Options)",
            command=self.go_to_options,
            width=18, height=2
        )
        next_btn.grid(row=10, column=1, pady=20, sticky="w")

    def toggle_ssn(self):
        if self.ssn_entry.cget("show") == "":
            self.ssn_entry.config(show="*")
        else:
            self.ssn_entry.config(show="")

    def add_allergy(self):
        allergy = self.allergy_entry.get().strip()
        if not allergy:
            return
        if allergy not in self.allergies_list:
            self.allergies_list.append(allergy)
            self.allergy_listbox.insert(tk.END, allergy)
        self.allergy_entry.delete(0, tk.END)

    def remove_allergy(self):
        selection = self.allergy_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an allergy to remove.")
            return
        index = selection[0]
        allergy_to_remove = self.allergies_list[index]
        self.allergies_list.remove(allergy_to_remove)
        self.allergy_listbox.delete(index)

    def preselect_insurance(self):
        current_id = self.app.patient.insurance
        if not current_id:
            return
        for item in self.insurance_list:
            if item["InsuranceID"] == current_id:
                self.insurance_var.set(item["Insurance Company Name"])
                return

    def save_patient_info(self):
        dob = self.dob_entry.get().strip()
        zipcode = self.zip_entry.get().strip()

        if dob and not Patient.validate_dob_format(dob):
            messagebox.showerror("Error", "DOB must be MM-DD-YYYY.")
            return
        if zipcode and not Patient.validate_zip_format(zipcode):
            messagebox.showerror("Error", "Zip Code must be 5 digits.")
            return

        p = self.app.patient
        p.dob = dob
        p.gender = self.gender_var.get().strip()
        p.Address = self.address_entry.get().strip()
        p.zipcode = zipcode
        p.ssn = self.ssn_entry.get().strip()
        p.allergies = list(self.allergies_list)

        selected_name = self.insurance_var.get().strip()
        if selected_name:
            for item in self.insurance_list:
                if item["Insurance Company Name"] == selected_name:
                    p.insurance = item["InsuranceID"]
                    break

        p.save_patient_info_snapshot()
        self.app.login_system.save_or_update_login_record(p)

        self.status_var.set("Patient information saved.")
        messagebox.showinfo("Saved", "Patient information saved successfully.")

    def go_to_options(self):
        if not self.app.patient.Pid:
            messagebox.showwarning("Warning", "No patient is logged in.")
            return
        self.app.show_options_screen()


# =========================
# OPTIONS SCREEN
# =========================
class OptionsScreen(tk.Frame):
    def __init__(self, parent, app: HospitalApp):
        super().__init__(parent)
        self.app = app

        title = tk.Label(self, text="Patient Options",
                         font=("Segoe UI", 18, "bold"))
        title.pack(pady=(20, 10))

        btn_display = tk.Button(
            self, text="Display Patient Information",
            width=30, height=2,
            command=self.display_info
        )
        btn_display.pack(pady=10)

        btn_edit = tk.Button(
            self, text="Edit Patient Information",
            width=30, height=2,
            command=self.edit_info
        )
        btn_edit.pack(pady=10)

        btn_diag = tk.Button(
            self, text="Patient Diagnostics (Next)",
            width=30, height=2,
            command=self.goto_diagnostics
        )
        btn_diag.pack(pady=10)

    def display_info(self):
        p = self.app.patient
        if not p.Pid:
            messagebox.showwarning("Warning", "No patient is logged in.")
            return

        info_text = (
            f"Patient ID: {p.Pid}\n"
            f"Name: {p.Pname}\n"
            f"DOB: {p.dob}\n"
            f"Email: {p.email}\n"
            f"Gender: {p.gender}\n"
            f"Address: {p.Address}\n"
            f"Zip: {p.zipcode}\n"
            f"Phone: {p.Pnumber}\n"
            f"SSN: {p.ssn}\n"
            f"Allergies: {', '.join(p.allergies) if p.allergies else 'None'}\n"
            f"Insurance ID: {p.insurance or 'None'}"
        )
        messagebox.showinfo("Patient Information", info_text)

    def edit_info(self):
        self.app.show_patient_info_screen()

    def goto_diagnostics(self):
        self.app.show_diagnostics_screen()


# =========================
# SYMPTOMS SCREEN
# =========================
class SymptomsScreen(tk.Frame):
    def __init__(self, parent, app: HospitalApp, symptom_obj: Symptoms):
        super().__init__(parent)
        self.app = app
        self.symptom_obj = symptom_obj

        self.all_symptom_data = self.symptom_obj.all_symptom_data
        self.selected_symptoms = {cat: [] for cat in self.all_symptom_data.keys()}
        self.current_category = None

        self._build_category_page()
        self._build_symptom_page()
        self.show_category_page()

    def _build_category_page(self):
        self.categories_page = tk.Frame(self)

        title = tk.Label(
            self.categories_page,
            text="Select a Symptom Category",
            font=("Times New Roman", 18, "bold")
        )
        title.pack(pady=10)

        container = tk.Frame(self.categories_page)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.category_list_frame = tk.Frame(canvas)

        self.category_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.category_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for category in self.all_symptom_data.keys():
            btn = tk.Button(
                self.category_list_frame,
                text=category,
                font=("Times New Roman", 12),
                height=2,
                relief="raised",
                command=lambda c=category: self.open_symptom_page(c)
            )
            btn.pack(fill="x", padx=5, pady=4)

    def _build_symptom_page(self):
        self.symptom_page = tk.Frame(self)

        self.symptom_title = tk.Label(
            self.symptom_page,
            text="",
            font=("Times New Roman", 16, "bold")
        )
        self.symptom_title.pack(pady=10)

        info_label = tk.Label(
            self.symptom_page,
            text="Hold Ctrl (Cmd on Mac) to select multiple symptoms.",
            font=("Times New Roman", 10),
            fg="gray"
        )
        info_label.pack(pady=(0, 5))

        self.symptom_listbox = tk.Listbox(
            self.symptom_page,
            selectmode="multiple",
            width=70,
            height=15
        )
        self.symptom_listbox.pack(padx=10, pady=10)

        btn_frame = tk.Frame(self.symptom_page)
        btn_frame.pack(pady=10)

        back_btn = tk.Button(
            btn_frame,
            text="Back to Categories",
            width=20,
            command=self.show_category_page
        )
        back_btn.grid(row=0, column=0, padx=5)

        save_btn = tk.Button(
            btn_frame,
            text="Save Selections",
            width=20,
            command=self.save_current_category_selections
        )
        save_btn.grid(row=0, column=1, padx=5)

        done_btn = tk.Button(
            btn_frame,
            text="Next (Doctor Recommendations)",
            width=25,
            command=self.finish_and_go_next
        )
        done_btn.grid(row=0, column=2, padx=5)

    def show_category_page(self):
        self.symptom_page.pack_forget()
        self.categories_page.pack(fill="both", expand=True)

    def show_symptom_page(self):
        self.categories_page.pack_forget()
        self.symptom_page.pack(fill="both", expand=True)

    def open_symptom_page(self, category_name):
        self.current_category = category_name
        self.symptom_title.config(text=f"Symptoms: {category_name}")

        self.symptom_listbox.delete(0, tk.END)
        symptoms = self.all_symptom_data[category_name]
        for s in symptoms:
            self.symptom_listbox.insert(tk.END, s)

        previously_selected = set(self.selected_symptoms.get(category_name, []))
        for idx, s in enumerate(symptoms):
            if s in previously_selected:
                self.symptom_listbox.selection_set(idx)

        self.show_symptom_page()

    def save_current_category_selections(self):
        if not self.current_category:
            return
        symptoms = self.all_symptom_data[self.current_category]
        chosen_indices = self.symptom_listbox.curselection()
        chosen = [symptoms[i] for i in chosen_indices]
        self.selected_symptoms[self.current_category] = chosen
        messagebox.showinfo("Saved", f"Saved {len(chosen)} symptom(s) for this category.")

    def finish_and_go_next(self):
        if self.current_category is not None:
            self.save_current_category_selections()

        self.symptom_obj.selected_symptoms = self.selected_symptoms
        self.app.show_doctor_recommendations(self.symptom_obj)


# =========================
# DOCTOR RECOMMENDATION SCREEN
# =========================
class DoctorRecommendationScreen(tk.Frame):
    def __init__(self, parent, app: HospitalApp, symptom_obj: Symptoms):
        super().__init__(parent)
        self.app = app
        self.symptom_obj = symptom_obj

        title = tk.Label(self, text="Recommended Doctors", font=("Segoe UI", 18, "bold"))
        title.pack(pady=(20, 10))

        info = tk.Label(
            self,
            text="Based on the selected symptom categories, these doctors are recommended.",
            font=("Segoe UI", 11)
        )
        info.pack(pady=(0, 10))

        used_categories, specialties = self.app.doctor_obj.gather_recommendations(
            self.app.patient,
            self.symptom_obj,
            self.app.category_doctor_map
        )

        self.doctors_flat = []
        for spec in specialties:
            for doc in self.app.doctor_obj.all_doctor_data.get(spec, []):
                self.doctors_flat.append(doc)

        columns = ("Name", "Specialty", "Hospital")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=220)

        for idx, doc in enumerate(self.doctors_flat):
            self.tree.insert("", "end", iid=str(idx),
                             values=(doc["Name"], doc["Specialty"], doc["Hospital"]))

        self.tree.pack(fill="both", expand=True, padx=20, pady=10)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Back to Symptoms", width=20,
                  command=self.app.show_symptoms_screen).grid(row=0, column=0, padx=5)

        tk.Button(btn_frame, text="View Selected Doctor", width=20,
                  command=self.view_selected_doctor).grid(row=0, column=1, padx=5)

    def view_selected_doctor(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a doctor from the list.")
            return
        idx = int(selection[0])
        doctor_info = self.doctors_flat[idx]
        self.app.show_doctor_details_screen(doctor_info)


# =========================
# DOCTOR DETAILS SCREEN
# =========================
class DoctorDetailsScreen(tk.Frame):
    def __init__(self, parent, app: HospitalApp, doctor_info: dict):
        super().__init__(parent)
        self.app = app
        self.doctor_info = doctor_info

        title = tk.Label(self, text="Doctor Details", font=("Segoe UI", 18, "bold"))
        title.pack(pady=(20, 10))

        details_frame = tk.Frame(self)
        details_frame.pack(pady=10, padx=20, anchor="w")

        def add_row(label_text, value, row):
            tk.Label(details_frame, text=label_text, font=("Segoe UI", 12, "bold")).grid(
                row=row, column=0, sticky="e", padx=5, pady=4
            )
            tk.Label(details_frame, text=value, font=("Segoe UI", 12)).grid(
                row=row, column=1, sticky="w", padx=5, pady=4
            )

        add_row("Name:", doctor_info["Name"], 0)
        add_row("Type of Doctor:", doctor_info["Specialty"], 1)
        add_row("Experience (years):", doctor_info["ExperienceYears"], 2)
        add_row("Hospital / Clinic:", doctor_info["Hospital"], 3)
        add_row("Email:", doctor_info["Email"], 4)
        add_row("Phone:", doctor_info["Phone"], 5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Back to Doctor List", width=20,
                  command=lambda: self.app.show_doctor_recommendations(self.app.last_symptom_obj)
                  ).grid(row=0, column=0, padx=5)

        tk.Button(btn_frame, text="Schedule Appointment", width=20,
                  command=lambda: self.app.show_calendar_screen(self.doctor_info)
                  ).grid(row=0, column=1, padx=5)

        tk.Button(btn_frame, text="Billing / Estimate Cost", width=20,
                  command=lambda: self.app.show_billing_screen(self.doctor_info)
                  ).grid(row=0, column=2, padx=5)


# =========================
# ✅ BILLING SCREEN (SAVE ONCE BUTTON)
# =========================
class BillingScreen(tk.Frame):
    def __init__(self, parent, app: HospitalApp, doctor_info: dict):
        super().__init__(parent)
        self.app = app
        self.doctor_info = doctor_info

        self.ins_disc_map = load_insurance_discount_map("Insurance_Companies.csv")
        self.doc_fee_map = load_doctor_fee_map("Doctor_Fees.csv")

        # ✅ only allow saving once per visit
        self.saved_once = False
        self.last_net_cost = None  # store last computed net for saving

        title = tk.Label(self, text="Billing Estimate", font=("Segoe UI", 18, "bold"))
        title.pack(pady=(20, 10))

        p = self.app.patient
        specialty = (doctor_info.get("Specialty", "") or "").strip()
        minutes = self.app.last_appointment_minutes
        appt_date = self.app.last_appointment_date
        appt_date_str = appt_date.isoformat() if appt_date else "Unknown"

        # Appointment length multipliers
        self.time_mult = {30: 1.5, 45: 2.0, 60: 2.5}

        summary = tk.Label(
            self,
            text=(
                f"Patient: {p.Pname} ({p.Pid})\n"
                f"Doctor: {doctor_info.get('Name','')} | Specialty: {specialty}\n"
                f"Insurance ID: {p.insurance or 'None'}\n"
                f"Appointment Date: {appt_date_str}\n"
                f"Appointment Length: {minutes} minutes"
            ),
            font=("Segoe UI", 11)
        )
        summary.pack(pady=(0, 10))

        self.result_var = tk.StringVar()
        result_lbl = tk.Label(
            self,
            textvariable=self.result_var,
            font=("Consolas", 11),
            justify="left"
        )
        result_lbl.pack(padx=20, pady=15, anchor="w")

        self.save_status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.save_status_var, fg="blue", font=("Segoe UI", 10)).pack(pady=(0, 8))

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame,
            text="Back to Doctor Details",
            width=22,
            command=lambda: self.app.show_doctor_details_screen(self.doctor_info)
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            btn_frame,
            text="Recalculate",
            width=15,
            command=self.recalc
        ).grid(row=0, column=1, padx=5)

        tk.Button(
            btn_frame,
            text="Save Billing Record",
            width=18,
            command=self.save_billing_once
        ).grid(row=0, column=2, padx=5)

        tk.Button(
            btn_frame,
            text="Sign Out / Exit",
            width=15,
            command=self.app.exit_app
        ).grid(row=0, column=3, padx=5)

        self.recalc()

    def recalc(self):
        p = self.app.patient

        # robust specialty match (lowercase/strip)
        specialty_key = (self.doctor_info.get("Specialty", "") or "").strip().lower()
        base_fee = self.doc_fee_map.get(specialty_key, 0.0)

        mins = self.app.last_appointment_minutes
        if mins not in (30, 45, 60):
            mins = 30
        mult = self.time_mult.get(mins, 1.0)

        gross = base_fee * mult

        ins_id = str(p.insurance).strip() if p.insurance else ""
        discount_pct = self.ins_disc_map.get(ins_id, 0.0) if ins_id else 0.0
        discount_amt = gross * (discount_pct / 100.0)

        net = gross - discount_amt

        # ✅ store for saving later
        self.last_net_cost = net

        self.result_var.set(
            f"Base fee (Specialty):   ${base_fee:,.2f}\n"
            f"Time multiplier:        x{mult:.2f}  ({mins} min)\n"
            f"-----------------------------------\n"
            f"Gross cost:             ${gross:,.2f}\n"
            f"Insurance discount:     {discount_pct:.1f}%  (-${discount_amt:,.2f})\n"
            f"-----------------------------------\n"
            f"Estimated patient cost: ${net:,.2f}"
        )

    def save_billing_once(self):
        if self.saved_once:
            messagebox.showinfo("Already Saved", "This billing record has already been saved.")
            return

        if self.last_net_cost is None:
            messagebox.showwarning("No Estimate", "Please calculate the billing estimate first.")
            return

        p = self.app.patient
        appt_date = self.app.last_appointment_date
        appt_date_iso = appt_date.isoformat() if appt_date else ""

        append_billing_record(
            patient_id=p.Pid,
            patient_name=p.Pname,
            doctor_name=self.doctor_info.get("Name", ""),
            appt_date_iso=appt_date_iso,
            billing_cost=self.last_net_cost,
            csv_path="Billing.csv"
        )

        self.saved_once = True
        self.save_status_var.set("✅ Billing record saved to Billing.csv")
        messagebox.showinfo("Saved", "Billing record saved successfully.")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    root = tk.Tk()
    app = HospitalApp(root)
    root.mainloop()
