# %%
from backend import DVH, Prescription, dose_police_in_action, request_needed_volume, actualizar_dvh_con_mapeos
import xlstools
import warnings
from tkinter import filedialog
import customtkinter as ctk

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

NAS_directory = "//FS-201-Radioterapia.intecnus.org.ar/"
constraint_excel_file_path = NAS_directory + "fisicos/8 - Físicos Médicos/Natalia Espector/2024 - Protocolos clínicos/Protocolo de constraints.xlsx"
dvh_folder_path = NAS_directory + "monaco/FocalData/DVH Output/"


class FileSelectorApp(ctk.CTk):
    def __init__(self, predefined_folder, options_list):
        super().__init__()

        self.title("Selector de Archivo y Opción")
        self.geometry("600x300")
        self.predefined_folder = predefined_folder
        self.options_list = options_list
        self.filtered_options = options_list.copy()
        self.selected_file = None
        self.selected_string = None

        # Widgets
        self.create_widgets()

    def create_widgets(self):
        # Botón para elegir archivo
        self.file_label = ctk.CTkLabel(self, text="Archivo seleccionado:")
        self.file_label.pack(pady=(10, 0))

        self.file_entry = ctk.CTkEntry(self, width=500)
        self.file_entry.pack(pady=5)

        self.browse_button = ctk.CTkButton(self, text="Elegir archivo", command=self.browse_file)
        self.browse_button.pack(pady=(0, 20))

        # Entrada de búsqueda para lista
        self.search_label = ctk.CTkLabel(self, text="Buscar en la lista:")
        self.search_label.pack(pady=(5, 0))

        self.search_entry = ctk.CTkEntry(self, width=300)
        self.search_entry.pack()
        self.search_entry.bind("<KeyRelease>", self.filter_dropdown)

        # Menú desplegable
        self.option_menu = ctk.CTkOptionMenu(self, values=self.filtered_options, command=self.on_select)
        self.option_menu.pack(pady=10)
        self.option_menu.set("PR+VS+LN 6000-20FX") 

        # Botón de confirmar
        self.confirm_button = ctk.CTkButton(self, text="Confirmar", command=self.confirm_selection)
        self.confirm_button.pack(pady=10)

    def browse_file(self):
        file_path = filedialog.askopenfilename(initialdir=self.predefined_folder)
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

        self.mappings = {}       # clave de dic_a → OptionMenu
        self.float_inputs = {}   # clave de dic_a (subset) → Entry

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
        ctk.CTkLabel(frame, text="Volumen (cc)").grid(row=0, column=2, padx=10, pady=5)

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

            if key_a in self.subset_keys_a:
                entry.grid(row=i + 1, column=2, padx=10, pady=5, sticky="w")

        # Botón de confirmar
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

        self.quit()
        self.destroy()

    @staticmethod
    def run(dic_a, dic_b, subset_keys_a):
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")

        root = ctk.CTk()
        root.withdraw()

        app = EstructurasApp(root, dic_a, dic_b, subset_keys_a)
        app.mainloop()

        return app.mapping_result, app.float_result

class ResultsWindow:
    def __init__(self, presc):
        self.new_dvh_requested = False

        self.window = ctk.CTk()
        self.window.title("Resultado de Constraints")
        self.window.geometry("800x600")

        textbox = ctk.CTkTextbox(self.window, wrap="word")
        textbox.pack(expand=True, fill="both", padx=20, pady=20)

        textbox.tag_config("green", foreground="green")
        textbox.tag_config("yellow", foreground="orange")
        textbox.tag_config("red", foreground="red")

        for p_name in list(presc.structures.keys()):
            textbox.insert("end", f'{p_name} constraints:\n', "title")
            for constraint in presc.structures[p_name]:
                if p_name in ['PTV_BOOST_TOTAL']:
                    continue
                if not constraint.ACCEPTABLE_LV_AVAILABLE:
                    if constraint.VERIFIED_IDEAL[0]:
                        mensaje = f"    PASA IDEAL: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}\n"
                        textbox.insert("end", mensaje, "green")
                    else:
                        mensaje = f"    NO PASA: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}\n"
                        textbox.insert("end", mensaje, "red")
                else:
                    if constraint.VERIFIED_IDEAL[0]:
                        mensaje = f"    PASA IDEAL: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}\n"
                        textbox.insert("end", mensaje, "green")
                    elif constraint.VERIFIED_ACCEPTABLE[0]:
                        mensaje = f"    PASA ACEPTABLE: {constraint.type}: {constraint.acceptable_dose} {constraint.acceptable_volume} -> {constraint.acceptable_dose} {constraint.VERIFIED_ACCEPTABLE[1]}\n"
                        textbox.insert("end", mensaje, "yellow")
                    else:
                        mensaje = f"    NO PASA: {constraint.type}: {constraint.acceptable_dose} {constraint.acceptable_volume} -> {constraint.acceptable_dose} {constraint.VERIFIED_ACCEPTABLE[1]}\n"
                        textbox.insert("end", mensaje, "red")

        textbox.configure(state="disabled")

        button_frame = ctk.CTkFrame(self.window)
        button_frame.pack(pady=10)

        close_button = ctk.CTkButton(button_frame, text="Cerrar", command=self.close)
        close_button.pack(side="left", padx=10)

        new_button = ctk.CTkButton(button_frame, text="Elegir nuevo DVH...", command=self.choose_new)
        new_button.pack(side="left", padx=10)

        self.window.mainloop()

    def close(self):
        self.window.destroy()

    def choose_new(self):
        self.new_dvh_requested = True
        self.window.destroy()

# ------------------------------------------------------------------------------------------------------ 

def main():
    carpeta_predeterminada = dvh_folder_path
    lista_opciones = xlstools.get_cell_content(file_path=constraint_excel_file_path, cell_coordinate='B2', sheet_name=None)[3:]

    app = FileSelectorApp(carpeta_predeterminada, lista_opciones)
    app.mainloop()
    # Resultado final:
    print(f"Template seleccionado y archivo:  {app.selected_string} - {app.selected_file}")

    # Instancio DVH y Prescription
    dvh = DVH(app.selected_file)
    presc = Prescription(constraint_excel_file_path, app.selected_string)

    # ----------------------------------------------------------- 
    # Actualizar volúmenes de estructuras si se quiere
    dvh.structures['PTV_PR'].volume_update(87.4)
    dvh.structures['PTV_VS'].volume_update(70.5)
    dvh.structures['INTESTINOS'].volume_update(1797.7)
    dvh.structures['SIGMA'].volume_update(205.2)
    dvh.structures['CAUDA_EQUINA'].volume_update(46.5) 
    # -----------------------------------------------------------

    volumen_requested_list = request_needed_volume(dvh, presc)
    mapping, valores = EstructurasApp.run(presc.structures, dvh.structures, volumen_requested_list)

    actualizar_dvh_con_mapeos(dvh, mapping, valores)   

    # Ejecutar la lógica principal de Dose Police
    dose_police_in_action([dvh], presc)

    # Mostrar resultados en una ventana emergente
    ventana = ResultsWindow(presc)
    NUEVO_DVH = ventana.new_dvh_requested

    print(NUEVO_DVH)

    while NUEVO_DVH:
        app = FileSelectorApp(carpeta_predeterminada, lista_opciones)
        app.mainloop()

        print(f"Template seleccionado y archivo:  {app.selected_string} - {app.selected_file}")

        dvh = DVH(app.selected_file)
        presc = Prescription(constraint_excel_file_path, app.selected_string)

        dose_police_in_action([dvh], presc)

        ventana = ResultsWindow(presc)
        NUEVO_DVH = ventana.new_dvh_requested

if __name__ == "__main__":
    main()


