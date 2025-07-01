"""
Welcome to this simplified version of my Phone Checker tool!
Works best with data extracted from Boond Manager : https://www.boondmanager.com/en/
Feel free to copy and modify it. 
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import csv
from collections import defaultdict
import re
import os
from pathlib import Path

# --- Configuration ---
# defines which columns to check in the CSV file
CONFIG = {
    "en": {
        "PHONE": ["Phone 1", "Phone 2"],
        "INFO": ["Last Name", "First Name", "Role", "Company - Name"],
        "COUNTRY": ["Country", "Company - Country"],
        "REF": "Internal reference"
    },
    "fr": {
        "PHONE": ["Téléphone 1", "Téléphone 2"],
        "INFO": ["Nom", "Prénom", "Fonction", "Société - Nom"],
        "COUNTRY": ["Pays", "Société - Pays"],
        "REF": "Référence interne"
    }
}
DEFAULT_CSV_FILE = "contacts.csv" # replace by your own file or select it in the GUI
MIN_PARTIAL_SEARCH_LENGTH = 3

# Below : encapsulation of the app
class PhoneCheckerApp:
    def __init__(self, root):
        self.root = root
        self.phone_data_store = defaultdict(list)
        self.loaded_csv_path = ""
        self.config = CONFIG["en"]  # default to English, but will check the file anyway

        self._setup_gui()

        #Load the default CSV file (if possible).
        if os.path.exists(DEFAULT_CSV_FILE):
            if self._load_data(DEFAULT_CSV_FILE):
                self._set_controls_state(tk.NORMAL)
            else:
                self.status_var.set(f"Error loading {DEFAULT_CSV_FILE}. Please use 'Load CSV'.")
        else:
            self.status_var.set(f"Default '{DEFAULT_CSV_FILE}' not found. Please use 'Load CSV'.")


    def _setup_gui(self):
        # Management of the graphic interface
        
        self.root.title("Boond Phone Checker")
        self.root.geometry("750x500")

        # --- Style and Fonts ---
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat")
        style.configure("TEntry", padding=6)
        results_font = ("Arial", 12)

        # --- Input Frame ---
        input_frame = ttk.Frame(self.root, padding="10")
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="Phone:").pack(side=tk.LEFT, padx=5)
        
        self.phone_entry = ttk.Entry(input_frame, width=30, font=results_font, state=tk.DISABLED)
        self.phone_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.phone_entry.bind("<Return>", self._on_search)

        self.search_button = ttk.Button(input_frame, text="Search", command=self._on_search, state=tk.DISABLED)
        self.search_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(input_frame, text="Load CSV", command=self._browse_file).pack(side=tk.LEFT, padx=5)
        
        # --- URL Options ---
        # Show or hide the URL in the results (especially useful if you're using another CRM solution)
        url_option_frame = ttk.Frame(input_frame)
        url_option_frame.pack(side=tk.RIGHT, padx=10)
        self.option_url_var = tk.BooleanVar(value=True)
        ttk.Label(url_option_frame, text="URL Link:").pack(anchor=tk.W)
        ttk.Radiobutton(url_option_frame, text="Show", variable=self.option_url_var, value=True, command=self._on_search).pack(anchor=tk.W)
        ttk.Radiobutton(url_option_frame, text="Hide", variable=self.option_url_var, value=False, command=self._on_search).pack(anchor=tk.W)

        # --- Results Frame ---
        results_frame = ttk.Frame(self.root, padding="10")
        results_frame.pack(expand=True, fill=tk.BOTH)

        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, state=tk.DISABLED, font=results_font)
        self.results_text.pack(expand=True, fill=tk.BOTH)
        self.results_text.tag_configure("warning", foreground="red", font=(results_font[0], results_font[1], "bold"))

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Please load a CSV file.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)


    # --- Data Handling ---

    # Standardize phone numbers
    def _get_digits(self, phone_str: str) -> str:
        if not phone_str or not isinstance(phone_str, str):
            return ""
        return re.sub(r'\D', '', phone_str.replace('(0)', '')) # removes the (0)

    def _get_csv_encoding(self, filepath):
        # Tries common encodings to open a file, useful because Boond allows different output
        # Also UTF-8-SIG is important to keep the reference from Boond, otherwise reference will be broken
        for encoding in ['utf-8-sig', 'iso-8859-15', 'windows-1250']:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    f.read()
                return encoding
            except (UnicodeDecodeError, IOError):
                continue
        return None

    def _load_data(self, filepath: str) -> bool:
        # Loads the data from the CSV file
        self.phone_data_store.clear()
        
        encoding = self._get_csv_encoding(filepath)

        if not encoding:
            messagebox.showerror("Error", f"Could not determine encoding for {filepath}")
            return False

        try:
            with open(filepath, mode='r', encoding=encoding, newline='') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                if not reader.fieldnames:
                    messagebox.showerror("Error", "CSV file is empty or has no headers.")
                    return False

                # English or French? Based on the expected columns
                if any(h in reader.fieldnames for h in CONFIG["fr"]["INFO"]):
                    self.config = CONFIG["fr"]
                    print("French headers detected.")
                else:
                    self.config = CONFIG["en"]
                    print("English headers assumed.")

                # Check the headers required (might remove ref later ?)
                expected_headers = self.config["PHONE"] + self.config["INFO"] + [self.config["REF"]]
                if missing := [h for h in expected_headers if h not in reader.fieldnames]:
                    messagebox.showwarning("Warning", f"CSV missing headers: {', '.join(missing)}.")

                # Actual loading of the data
                for i, row in enumerate(reader):
                    contact_info = {col: row.get(col, '').strip() for col in self.config["INFO"]} # Names 
                    contact_info[self.config["REF"]] = row.get(self.config["REF"], '').strip() # Reference

                    # Phones: normalize and store
                    processed_numbers = set()
                    for p_col in self.config["PHONE"]:
                        phone_val = row.get(p_col, "")
                        norm_phone = self._get_digits(phone_val)
                        if norm_phone and norm_phone not in processed_numbers:
                            self.phone_data_store[norm_phone].append(contact_info)
                            processed_numbers.add(norm_phone)
            
            self.loaded_csv_path = filepath
            self.status_var.set(f"Loaded: {Path(filepath).name}. {len(self.phone_data_store)} Numbers.")
            return True

        except Exception as e:
            messagebox.showerror("Error Loading Data", f"An error occurred: {e}")
            self.loaded_csv_path = ""
            self.status_var.set("Failed to load data.")
            return False

    # --- Search ---
    def _generate_search_keys(self, query: str) -> set:
        # Explores the possibilities based on the number entered

        digits = self._get_digits(query)
        keys = {digits}
        
        # Deal with international prefixes
        s = query.strip().replace('(0)', '')
        if s.startswith('00'):
            keys.add(s[2:])
        elif s.startswith('+'):
            keys.add(s[1:])
        
        # Add prefixes for countriess
        if digits.startswith('0') and len(digits) > 9:
            national_part = digits[1:]
            keys.add(f'33{national_part}') # France
            keys.add(f'49{national_part}') # Germany

        return {k for k in keys if k}

    def _on_search(self, event=None):
        # Base function when launching the search

        query = self.phone_entry.get().strip()
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)

        if not self.phone_data_store:
            self._display_message("No data loaded. Please load a CSV file first.", "No data loaded.")
            return
        if not query:
            self._display_message("Please enter a phone number or part of it.", "Empty search query.")
            return

        # Dictionary based on internal reference 
        found_by_ref = defaultdict(lambda: {"info": None})
        
        # Matches
        query_digits = self._get_digits(query)
        if len(query_digits) >= MIN_PARTIAL_SEARCH_LENGTH:
            for stored_phone, contacts in self.phone_data_store.items():
                if query_digits in stored_phone:
                    for contact in contacts:
                        ref = contact[self.config["REF"]]
                        found_by_ref[ref]["info"] = contact

        self._display_results(found_by_ref, query)
        self.results_text.config(state=tk.DISABLED)

    # --- Results Display ---
    def _display_results(self, found_by_ref: dict, query: str):
        
        # Nothing found 
        if not found_by_ref:
            self._display_message("No contact found for your query.", "No contact found.")
            return
        
        # Warning if more than 1 
        if len(found_by_ref) > 1:
            self.results_text.insert(tk.END, f"WARNING: {len(found_by_ref)} different contacts found.\n\n", "warning")

        # Simple List
        self.results_text.insert(tk.END, "\n\n---------------------------------------------------------------------------------------- \n   👍 SIMPLE LIST\n         Copy-Paste in your notes\n---------------------------------------------------------------------------------------- \n\n")
        
        self.results_text.insert(tk.END, f"ℹ️ Phone number: {query}\n\n")

        for ref, data in found_by_ref.items():
            info = data["info"]
            c_first, c_last = info.get(self.config["INFO"][1], 'N/A'), info.get(self.config["INFO"][0], 'N/A')
            self.results_text.insert(tk.END, f"- {c_first} {c_last}\n")
            
            #creation of the URL (only for boond)
            if self.option_url_var.get() and (ref_digits := self._get_digits(ref)):
                url = f"https://ui.boondmanager.com/contacts/{ref_digits}/overview"
                self.results_text.insert(tk.END, f"{url}\n\n")

        #  Detailed List
        self.results_text.insert(tk.END, "\n\n---------------------------------------------------------------------------------------- \n   👌 DETAILED INFORMATIONS\n ---------------------------------------------------------------------------------------- \n\n\n")

        for ref, data in found_by_ref.items():
            info = data["info"]
            c_first, c_last, c_role, c_company = (
                info.get(self.config["INFO"][1], 'N/A'), info.get(self.config["INFO"][0], 'N/A'),
                info.get(self.config["INFO"][2], 'N/A'), info.get(self.config["INFO"][3], 'N/A')
            )
            
            display_str = (
                f"Name: {c_first} {c_last}\n"
                f"Role: {c_role}\n"
                f"Company: {c_company}\n"
                f"Ref: {ref}\n---\n"
            )
            self.results_text.insert(tk.END, display_str)
        
        # update the status bar
        self.status_var.set(f"Found {len(found_by_ref)} contact(s).")
        
    def _display_message(self, text_msg, status_msg):
        # will display a message in the box

        self.results_text.insert(tk.END, text_msg)
        self.status_var.set(status_msg)
        self.results_text.config(state=tk.DISABLED)

    def _browse_file(self):
        # browse the files to select csv

        if filepath := filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))):

            if self._load_data(filepath):
                self._set_controls_state(tk.NORMAL)
            else:
                self._set_controls_state(tk.DISABLED)

    def _set_controls_state(self, state): #TO DELETE BECAUSE NOT ENOUGH BUTTONS ? 
        # Enable or disable search controls.
        self.phone_entry.config(state=state)
        self.search_button.config(state=state)

def main():
    root = tk.Tk()
    PhoneCheckerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()