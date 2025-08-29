from backend import DVH, Prescription, dose_police_in_action, request_needed_volume, actualizar_dvh_con_mapeos
import xlstools
import warnings
import customtkinter as ctk
import json
import os
import sys

# extra imports para PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from customtkinter import filedialog as ctkfiledialog
from datetime import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Define the paths for the NAS directory and the Excel file
NAS_directory = resource_path("//FS-201-Radioterapia.intecnus.org.ar/")
constraint_excel_file_path = resource_path(NAS_directory + "fisicos/8 - Físicos Médicos/Natalia Espector/2024 - Protocolos clínicos/Protocolo de constraints.xlsx")
dvh_folder_path = resource_path(NAS_directory + "monaco/FocalData/DVH Output/")


class FileSelectorApp(ctk.CTkToplevel):
    def __init__(self, master, predefined_folder, options_list):
        super().__init__(master)

        self.title("Selector de Archivo y Opción")
        self.geometry("600x300")
        self.predefined_folder = predefined_folder
        self.options_list = options_list
        self.filtered_options = options_list.copy()
        self.selected_file = None
        self.selected_string = None

        self.create_widgets()

    def create_widgets(self):
        self.file_label = ctk.CTkLabel(self, text="Archivo seleccionado:")
        self.file_label.pack(pady=(10, 0))

        self.file_entry = ctk.CTkEntry(self, width=500)
        self.file_entry.pack(pady=5)

        self.browse_button = ctk.CTkButton(self, text="Elegir archivo", command=self.browse_file)
        self.browse_button.pack(pady=(0, 20))

        self.search_label = ctk.CTkLabel(self, text="Buscar en la lista:")
        self.search_label.pack(pady=(5, 0))

        self.search_entry = ctk.CTkEntry(self, width=300)
        self.search_entry.pack()
        self.search_entry.bind("<KeyRelease>", self.filter_dropdown)

        self.option_menu = ctk.CTkOptionMenu(self, values=self.filtered_options, command=self.on_select)
        self.option_menu.pack(pady=10)
        self.option_menu.set("PR+VS+LN 6000-20FX")

        self.confirm_button = ctk.CTkButton(self, text="Confirmar", command=self.confirm_selection)
        self.confirm_button.pack(pady=10)

    def browse_file(self):
        file_path = ctkfiledialog.askopenfilename(initialdir=self.predefined_folder)
        if file_path:
            self.selected_file = file_path
            self.file_entry.delete(0, ctk.END)
            self.file_entry.insert(0, file_path)

    def filter_dropdown(self, event=None):
        search_term = self.search_entry.get().lower()
        self.filtered_options = [opt for opt in self.options_list if search_term in opt.lower()]
        if self.filtered_options:
            self.option_menu.configure(values=self.filtered_options)
            self.option_menu.set(self.filtered_options[0])
        else:
            self.option_menu.set("Sin coincidencias")

    def on_select(self, value):
        self.selected_string = value

    def confirm_selection(self):
        self.selected_string = self.option_menu.get()
        self.selected_file = self.file_entry.get()
        self.destroy()


class EstructurasApp(ctk.CTkToplevel):
    def __init__(self, master, dic_a, dic_b, subset_keys_a):
        super().__init__(master)
        self.title("Mapeo de estructuras")
        self.geometry("850x800")

        self.dic_a = dic_a
        self.dic_b = dic_b
        self.subset_keys_a = subset_keys_a

        self.mappings = {}
        self.float_inputs = {}

        self.mapping_result = None
        self.float_result = None

        self.create_widgets()

    def create_widgets(self):
        title = ctk.CTkLabel(self, text="Mapeo de estructuras:", font=("Arial", 18))
        title.pack(pady=10)

        frame = ctk.CTkScrollableFrame(self, width=800, height=600)
        frame.pack(pady=(10, 5), padx=10, fill="x")

        ctk.CTkLabel(frame, text="Prescripción").grid(row=0, column=0, padx=10, pady=5)
        ctk.CTkLabel(frame, text="DVH").grid(row=0, column=1, padx=10, pady=5)

        for i, key_a in enumerate(self.dic_a.keys()):
            ctk.CTkLabel(frame, text=key_a).grid(row=i + 1, column=0, padx=10, pady=5, sticky="w")

            values = ['-'] if key_a in self.dic_b else list(self.dic_b.keys())
            default_value = values[0]

            option_menu = ctk.CTkOptionMenu(frame, values=values)
            option_menu.set(default_value)
            option_menu.grid(row=i + 1, column=1, padx=10, pady=5, sticky="w")
            self.mappings[key_a] = option_menu

            entry = ctk.CTkEntry(frame, width=100, placeholder_text="Valor")
            self.float_inputs[key_a] = entry

        boton = ctk.CTkButton(self, text="Confirmar", command=self.actualizar)
        boton.pack(pady=(10, 20))

    def actualizar(self):
        self.mapping_result = {k: self.mappings[k].get() for k in self.mappings}
        self.float_result = {}

        for k in self.subset_keys_a:
            val_str = self.float_inputs[k].get().strip()
            if val_str:
                try:
                    self.float_result[k] = float(val_str)
                except ValueError:
                    self.float_result[k] = None

        self.destroy()

    @staticmethod
    def run(master, dic_a, dic_b, subset_keys_a):
        app = EstructurasApp(master, dic_a, dic_b, subset_keys_a)
        app.grab_set()
        app.wait_window()
        return app.mapping_result, app.float_result


class ResultsWindow(ctk.CTkToplevel):
    def __init__(self, master, presc, dvh):
        super().__init__(master)

        self.new_dvh_requested = False
        self.dvh = dvh

        self.title("Resultado de Constraints")
        self.geometry("800x600")

        self.textbox = ctk.CTkTextbox(self, wrap="word")
        self.textbox.pack(expand=True, fill="both", padx=20, pady=20)

        self.textbox.tag_config("green", foreground="green")
        self.textbox.tag_config("yellow", foreground="orange")
        self.textbox.tag_config("red", foreground="red")

        for p_name in presc.structures:
            self.textbox.insert("end", f'{p_name} constraints:\n', ("title",))
            for constraint in presc.structures[p_name]:
                if p_name in ['PTV_BOOST_TOTAL']:
                    continue
                if not constraint.ACCEPTABLE_LV_AVAILABLE:
                    if constraint.VERIFIED_IDEAL[0]:
                        mensaje = f"    PASA IDEAL: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}\n"
                        self.textbox.insert("end", mensaje, ("green",))
                    else:
                        mensaje = f"    NO PASA: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}\n"
                        self.textbox.insert("end", mensaje, ("red",))
                else:
                    if constraint.VERIFIED_IDEAL[0]:
                        mensaje = f"    PASA IDEAL: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}\n"
                        self.textbox.insert("end", mensaje, ("green",))
                    elif constraint.VERIFIED_ACCEPTABLE[0]:
                        mensaje = f"    PASA ACEPTABLE: {constraint.type}: {constraint.acceptable_dose} {constraint.acceptable_volume} -> {constraint.acceptable_dose} {constraint.VERIFIED_ACCEPTABLE[1]}\n"
                        self.textbox.insert("end", mensaje, ("yellow",))
                    else:
                        mensaje = f"    NO PASA: {constraint.type}: {constraint.acceptable_dose} {constraint.acceptable_volume} -> {constraint.acceptable_dose} {constraint.VERIFIED_ACCEPTABLE[1]}\n"
                        self.textbox.insert("end", mensaje, ("red",))

        self.textbox.configure(state="disabled")

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=10)

        close_button = ctk.CTkButton(button_frame, text="Cerrar", command=self.close)
        close_button.pack(side="left", padx=10)

        new_button = ctk.CTkButton(button_frame, text="Elegir nuevo DVH...", command=self.choose_new)
        new_button.pack(side="left", padx=10)

        save_pdf_button = ctk.CTkButton(button_frame, text="Guardar PDF", command=self.save_as_pdf)
        save_pdf_button.pack(side="left", padx=10)

    def close(self):
        self.destroy()

    def choose_new(self):
        self.new_dvh_requested = True
        self.destroy()

    def save_as_pdf(self):
        default_name = f"Resultados_{self.dvh.plan_name}_{self.dvh.patient_id}.pdf"
        file_path = ctkfiledialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Guardar resultados como PDF"
        )
        if not file_path:
            return

        content = self.textbox.get("1.0", "end-1c")
        lines = content.split("\n")

        c = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter

        # --- LOGO INTECNUS ---
        try:
            logo_path = resource_path("logo_intecnus.png")
            c.drawImage(logo_path, 40, height - 100, width=120, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print("No se pudo cargar el logo:", e)

        # --- ENCABEZADO ---
        y = height - 50
        c.setFont("Helvetica-Bold", 16)
        c.drawString(180, y, "Resultados de Constraints")  # desplazado para no tapar logo
        y -= 25
        c.setFont("Helvetica", 12)
        c.drawString(180, y, f"Plan: {self.dvh.plan_name}")
        y -= 20
        c.drawString(180, y, f"Paciente ID: {self.dvh.patient_id}")
        y -= 20
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        c.drawString(180, y, f"Fecha de generación: {fecha}")
        y -= 40

        # --- CUERPO CON COLORES ---
        c.setFont("Helvetica", 10)
        for i, line in enumerate(lines):
            start_idx = f"{i+1}.0"
            tags = self.textbox.tag_names(start_idx)

            color = colors.black
            if "green" in tags:
                color = colors.green
            elif "yellow" in tags:
                color = colors.orange
            elif "red" in tags:
                color = colors.red

            c.setFillColor(color)
            c.drawString(40, y, line)
            y -= 14
            if y < 40:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

        c.save()



def get_temp_json_path(dvh):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_folder = os.path.join(script_dir, "Temp")
    os.makedirs(temp_folder, exist_ok=True)

    filename = f"{dvh.plan_name}_{dvh.patient_id}.json"
    return os.path.join(temp_folder, filename)

def save_mapping_and_volumes(dvh, name_mapping, volume_mapping):
    path = get_temp_json_path(dvh)
    data = {"name_mapping": name_mapping, "volume_mapping": volume_mapping}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_mapping_and_volumes_if_exists(dvh):
    path = get_temp_json_path(dvh)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["name_mapping"], data["volume_mapping"]
    return None, None

# ------------------------------------------------------------------------------------------------------ 

def main():
    carpeta_predeterminada = dvh_folder_path
    lista_opciones = xlstools.get_cell_content(file_path=constraint_excel_file_path, cell_coordinate='B2', sheet_name=None)[3:]

    root = ctk.CTk()
    root.withdraw()

    while True:
        selector = FileSelectorApp(root, carpeta_predeterminada, lista_opciones)
        selector.grab_set()
        selector.wait_window()

        if not selector.selected_file or not selector.selected_string:
            break

        dvh = DVH(selector.selected_file)
        presc = Prescription(constraint_excel_file_path, selector.selected_string)

        name_mapping, volume_mapping = load_mapping_and_volumes_if_exists(dvh)

        if name_mapping is None or volume_mapping is None:
            volumen_requested_list = request_needed_volume(dvh, presc)
            name_mapping, volume_mapping = EstructurasApp.run(root, presc.structures, dvh.structures, volumen_requested_list)
            save_mapping_and_volumes(dvh, name_mapping, volume_mapping)

        actualizar_dvh_con_mapeos(dvh, name_mapping, volume_mapping)

        dose_police_in_action([dvh], presc)

        ventana_resultado = ResultsWindow(root, presc, dvh)
        ventana_resultado.grab_set()
        ventana_resultado.wait_window()

        if not ventana_resultado.new_dvh_requested:
            break


if __name__ == "__main__":
    main()
