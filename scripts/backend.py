import tkinter as tk
from tkinter import ttk
import os
from tkinter import filedialog
from typing import List
import xlstools
from xlstools import open_workbook
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import openpyxl
from termcolor import colored
from scipy.interpolate import interp1d

import customtkinter as ctk
from typing import List

SPATIAL_RESOLUTION = 0.1 #cm
BIN_WIDTH = 1 #cGy
DOSE_UNIT = 'cGy'
VOLUME_UNIT = '%'
MAX_DOSE_ABS_VOLUME = 0.03 #cm3
corrected_dict = {}

def lista_contenida(lista_pequena, lista_grande):
    # Convertimos las listas en conjuntos para aprovechar la eficiencia de las operaciones de conjuntos
    conjunto_pequeno = set(lista_pequena)
    conjunto_grande = set(lista_grande)
    
    # Verificamos si conjunto_pequeno es un subconjunto de conjunto_grande
    return conjunto_pequeno.issubset(conjunto_grande)


class Structure:
    def __init__(self, label, dose_axis, cumulated_percent_volume_axis):
        self.label = 'Paciente' if label == 'Paciente(Unsp.Tiss.)' else label
        self.volume = None
        self.dose_axis = dose_axis
        self.cumulated_percent_volume_axis = cumulated_percent_volume_axis
        self.differential_percent_volume_axis = -np.diff(self.cumulated_percent_volume_axis, 
                                              axis=0, 
                                              prepend=self.cumulated_percent_volume_axis[0])
        self.mean = self._mean_calculation()
        self.constraints = []

    def _mean_calculation(self):
        sum_dummy = (self.differential_percent_volume_axis*self.dose_axis).sum()
        sum_dummy /= self.differential_percent_volume_axis.sum()
        sum_dummy -= 1
        return sum_dummy

    def volume_update(self, volume: float) -> None:
        self.volume = volume
    
    def label_update(self, name: float) -> None:
        self.label = name


    def volume_function(self, dose):   # Entrada de dosis en cGy, devuelve en porcentaje de volumen
        y_min = self.cumulated_percent_volume_axis[0]
        y_max = self.cumulated_percent_volume_axis[-1]
        dvh = interp1d(self.dose_axis, self.cumulated_percent_volume_axis, kind='linear', bounds_error=False, fill_value=(y_min, y_max))
        return round(dvh(dose).item(), 1)
    
    def dose_function(self, volume):   # Entrada de volumen en porcentaje, devuelve dosis en cGy
        y_min = self.dose_axis[0]
        y_max = self.dose_axis[-1]
        vdh = interp1d(self.cumulated_percent_volume_axis, self.dose_axis, kind='linear', bounds_error=False, fill_value=(y_min, y_max))
        return round(vdh(volume).item(), 1)

class DVH:
    def __init__(self, file_path):
        # self.file_path = self._file_finder('Seleccione el archivo DVH.')
        self.file_path = file_path
        self.patient_id, self.plan_name, self.date_and_time, self.structures = self._DVH_data_parser()

    def _file_finder(self, window_title: str) -> str:
        tk.Tk().withdraw() # prevents an empty tkinter window from appearing
        my_directory = filedialog.askopenfilename(initialdir=os.getcwd(), 
                                           title=window_title, 
                                           filetypes=[("TXT Files", "*.txt")])
        return(my_directory)

    def _DVH_data_parser(self) -> List:
            try:
                with open(self.file_path, 'r') as file:
                    data = file.readlines()
                    header = data[0]

                    patient_id = header.split(' ')[2]
                    plan_name = header.split(' ')[6]
                    date_and_time = data[-1]

                    data_dict = {}
                    for row in data[3:-3]:
                        row = row.replace('\n','').split('                    ')
                        key = row[0]
                        values = [float(row[1]), float(row[2])]
                        
                        # Verificar si la key ya existe en el diccionario
                        if key in data_dict.keys():
                            data_dict[key].append(values)
                        else:
                            data_dict[key] = [values]

                    structures_dict = {}
                    for key in data_dict:
                        # convierto a numpy.array para poder transponer
                        dummy = np.array(data_dict[key]).T
                        if key in ['Camilla', 'Espuma', 'isoctsim']:     # Estructuras que no nos interesa evaluar
                            continue
                        structures_dict[key.upper()]= Structure(key.upper(),dummy[0],dummy[1])
                           
                    return patient_id, plan_name, date_and_time, structures_dict
                
            except FileNotFoundError:
                print(f"El archivo '{self.archivo}' no fue encontrado.")
            except Exception as e:
                print(f"Error al leer el archivo: {e}")

    def plot(self, DIFFERENTIAL_DVH: bool=False) -> None:
        print('RESUMEN DEL DVH INGRESADO:')
        print(f'\tPatient ID: {self.patient_id}')
        print(f'\tPlan Name: {self.plan_name}')
        print(f'\tFecha y Hora: {self.date_and_time}')
        print('\n')

        plt.figure()
        for structure in list(self.structures.values()):
            # print(f'{structure.label}:\t{structure.mean:.1f} cGy')
            if DIFFERENTIAL_DVH:
                plt.plot(structure.dose_axis, 
                         structure.differential_percent_volume_axis, 
                         label=structure.label)
                plt.title('Differential dose-volume histogram')
                plt.ylim([0,1.5])
            else:
                plt.plot(structure.dose_axis, 
                         structure.cumulated_percent_volume_axis, 
                         label=structure.label)
                plt.title('Cumulated dose-volume histogram')
     
        plt.xlabel('Dosis[cGy]')
        plt.ylabel('Volume[%]')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid()
        plt.show()

class Constraint:
    def __init__(self, constraints_chart_line):
        self.structure_name, self.type, self.ideal_dose, self.ideal_volume, self.acceptable_dose, self.acceptable_volume = constraints_chart_line
        self.structure_name = self.structure_name.upper()
        self.VERIFIED_IDEAL = (False, 0.0)
        self.VERIFIED_ACCEPTABLE = (False, 0.0)
        self.ACCEPTABLE_LV_AVAILABLE = self.acceptable_dose != 'None'

    def _evaluate(self, structure, ref1, ref2):   #ref1 y ref2 despues podran ser contraint ideal o aceptable
        constraint_types = ['V(D)>V_%', 'V(D)>V_cc', 'V(D)<V_%', 'V(D)<V_cc', 'D(V_%)<D', 'D(V_cc)<D', 'Dmax', 'Dmedia']

        if self.type in constraint_types[:4]:
            is_superior = self.type in (constraint_types[2], constraint_types[3])
            abs_volume = self.type in (constraint_types[1], constraint_types[3])

            ref_dose = float(ref1)
            ref_vol  = float(ref2)
            result = structure.volume_function(ref_dose)
            result = result * structure.volume/100.0 if abs_volume else result

            # print(f'dvh percent: {result}')

            if (is_superior and result <= ref_vol) or ((not is_superior) and result >= ref_vol):
                PASS = True
            else:
                PASS = False
            #print(PASS, result, ref_vol, ref_dose)
            return (PASS, round(result, 1))
            
            
        elif self.type in constraint_types[4:6]:
            abs_volume = self.type == constraint_types[5]

            ref_vol   = float(ref1)  #cc
            ref_vol   = float( ref_vol*100.0/structure.volume if abs_volume else ref_vol ) #%
            ref_dose = float(ref2)
            result = structure.dose_function(ref_vol)
            # print(f'vdh percent: {result}')
            if result <= ref_dose:
                PASS = True
            else:
                PASS = False
            return (PASS, round(result, 1))
            
        elif self.type in constraint_types[6:]:
            dmax       = self.type == constraint_types[6]
            dmed       = self.type == constraint_types[7]

            if dmax:
                ref_vol   = float( MAX_DOSE_ABS_VOLUME * 100.0/structure.volume)  #%
            ref_dose  = float(ref1)
            result = structure.mean if dmed else structure.dose_function(ref_vol)
            # print(f'med o max: {result}')
            if result <= ref_dose:
                PASS = True
            else:
                PASS = False
            return (PASS, round(result, 1))
            
        else:
            PASS = False
            print('No existe el tipo de constraint en las lista de tipos de constraints.')
            return (PASS, 'None')


    def verify(self, structure: Structure):   
        #print(f'Verifico ideal?: {self.VERIFIED_IDEAL[0]}, Hay level aceptable?: {self.ACCEPTABLE_LV_AVAILABLE}')
        self.VERIFIED_IDEAL = self._evaluate(structure, self.ideal_dose, self.ideal_volume)

        if not self.VERIFIED_IDEAL[0] and self.ACCEPTABLE_LV_AVAILABLE:
            
            self.VERIFIED_ACCEPTABLE = self._evaluate(structure, self.acceptable_dose, self.acceptable_volume) 

        #print(f'Constraint: {self.type} - {self.structure_name} - Ideal: {self.ideal_dose} {self.ideal_volume} - Aceptable: {self.acceptable_dose} {self.acceptable_volume}')
            
class Prescription:
    def __init__(self, constraint_excel_filepath, presc_template_name):
        self.constraint_excel_filepath = constraint_excel_filepath
        self.presc_template_name = presc_template_name.upper()
        self.structures = {}

        constraints_chart = self._prescription_importer()

        target_chart = constraints_chart.pop(0)
        constraints_chart = [sublist[1:] for sublist in constraints_chart[0]]


        self.target_structures = {}
        for target_structure in target_chart:
            self.target_structures[target_structure[0]] = [int(x) for x in target_structure[1:3]]

        for constraint_chart_line in constraints_chart:
            new_structure_name = constraint_chart_line[0]
            if new_structure_name != 'None':
                structure_name = new_structure_name.upper()
                self.structures[structure_name] = []
                self.structures[structure_name].append(Constraint(constraint_chart_line))
            else:
                self.structures[structure_name].append(Constraint(constraint_chart_line))   

            
    def _prescription_importer(self):
        workbook = openpyxl.load_workbook(self.constraint_excel_filepath)
        # for name in workbook.sheetnames:
        #     print(name)
        excel_data = xlstools.cell_data_importer(open_workbook(self.constraint_excel_filepath, self.presc_template_name),
                                                (4,'A'), 
                                                (45,'G'))

        chunks_charts = xlstools.none_based_data_parser(excel_data)

        assert len(chunks_charts)==2, "Error de importacion de chunks. Numero de chunks: "+f'{len(chunks_charts)}'
        if len(chunks_charts)==2:
            constraints_chart = [chunks_charts[0][1:], chunks_charts[1][2:]]

        return constraints_chart

    def print(self):
        print(f'Resumen de datos ingresados de la prescripcion:'.upper())
        print(f'\tPresc. Name: {self.presc_template_name}')
        print(f'\tPath: {self.constraint_excel_filepath}')
        print('\tVolumenes Target: [Dosis total, Dosis diaria]')
        for structure_name, content in self.target_structures.items():
            print(f'\t\t{structure_name}:\t',content)
        print('\n')
        
        dummy = []
        for structure_name, constraints in self.structures.items():
            for constraint in constraints:
                if constraint.VERIFIED_IDEAL[0]:
                    check = f'    PASS IDEAL: {constraint.VERIFIED_IDEAL[1]}'  
                elif constraint.VERIFIED_ACCEPTABLE[0]:
                    check = f'    PASS ACEPTABLE: {constraint.VERIFIED_ACCEPTABLE[1]}'
                else:
                    check = f'    FAIL: {constraint.VERIFIED_ACCEPTABLE[1]}'
                dummy.append([structure_name, constraint.type, constraint.ideal_dose, constraint.ideal_volume, constraint.acceptable_dose, constraint.acceptable_volume, check])
        print(pd.DataFrame(dummy).to_string(header=False, index=False))

def actualizar_dvh_con_mapeos(dvh: DVH, mapeo: dict, volumenes: dict) -> None:
    """
    Aplica los mapeos de nombres y actualiza los volúmenes dentro de dvh.structures.

    Parameters:
        dvh (DVH): Objeto DVH a modificar.
        mapeo (dict): Diccionario {nombre_antiguo_en_dvh: nombre_nuevo}.
        volumenes (dict): Diccionario {nombre_actual_en_dvh: volumen_cc}.
    """
    nuevas_structures = {}

    for dvh_str_name, estructura in dvh.structures.items():
        # Actualizar volumen si corresponde
        if dvh_str_name in volumenes:
            estructura.volume_update(volumenes[dvh_str_name])

        # Actualizar nombre si corresponde
        nuevo_nombre = mapeo.get(dvh_str_name, dvh_str_name)
        if nuevo_nombre != "-":
            estructura.label_update(nuevo_nombre)
            nuevas_structures[nuevo_nombre] = estructura
        else:
            nuevas_structures[dvh_str_name] = estructura

    # Reemplazar estructuras del dvh
    dvh.structures = nuevas_structures

def match_strings_and_volume_entry(dvh_list_dummy, presc):
    def request_needed_volume(dvh_list_dummy, presc):
        need_volume_types = ['V(D)>V_cc', 'V(D)<V_cc', 'D(V_cc)<D', 'Dmax']
        needing_volume = []

        # Paso 1: Detectar las estructuras que requieren volumen
        for label, constraints in presc.structures.items():
            for constraint in constraints:
                if constraint.type in need_volume_types:
                    needing_volume.append(label)
                    break

        # Paso 2: Filtrar estructuras que ya tienen volume distinto de 0
        filtered = []
        dvh_structures = dvh_list_dummy[0].structures
        for label in needing_volume:
            if label in dvh_structures:
                vol = dvh_structures[label].volume
                if vol is None or vol == 0:
                    filtered.append(label)
            else:
                filtered.append(label)  # Si no está en DVH, igual lo necesita

        return list(set(filtered))

    def launch_gui(presc_names, dvh_names, needs_volume):
        root = tk.Tk()
        root.title("Emparejar estructuras y asignar volúmenes")
        tk.Label(root, text="Empareje estructuras del protocolo con el DVH. Ingrese volumen si corresponde.")\
            .grid(row=0, columnspan=3, pady=10)

        dropdown_vars = {}
        volume_entries = {}

        row = 1
        for presc_name in presc_names:
            name_needs_match = presc_name not in dvh_names
            name_needs_volume = presc_name in needs_volume

            if not name_needs_match and not name_needs_volume:
                continue

            tk.Label(root, text=presc_name).grid(row=row, column=0)

            # Dropdown para renombrar (activado solo si es necesario)
            var = tk.StringVar(value=presc_name)
            dropdown = ttk.Combobox(root, textvariable=var, values=dvh_names, state="readonly")
            dropdown.grid(row=row, column=1)
            if not name_needs_match:
                dropdown.configure(state="disabled")
            dropdown_vars[presc_name] = var

            # Entry de volumen si es necesario
            if name_needs_volume:
                entry = tk.Entry(root)
                entry.grid(row=row, column=2)
                volume_entries[presc_name] = entry

            row += 1

        def on_submit():
            for presc_name in dropdown_vars:
                selected_dvh_key = dropdown_vars[presc_name].get()
                if not selected_dvh_key:
                    print(f"⚠️ No se asignó estructura para: {presc_name}")
                    continue
                replacement_dict[presc_name] = selected_dvh_key

                if presc_name in volume_entries:
                    try:
                        vol = float(volume_entries[presc_name].get())
                        volume_dict[presc_name] = vol
                    except ValueError:
                        print(f"⚠️ Entrada inválida de volumen para {presc_name}")
            root.destroy()

        tk.Button(root, text="OK", command=on_submit).grid(row=row + 1, columnspan=3, pady=10)
        root.mainloop()
        return replacement_dict, volume_dict

    def apply_corrections(dvh, replacement_dict, volume_dict):
        new_structures = {}
        for old_key, structure in dvh.structures.items():
            matched_presc = next((k for k, v in replacement_dict.items() if v == old_key), None)
            new_key = matched_presc if matched_presc else old_key
            structure.label = new_key
            new_structures[new_key] = structure
            if new_key in volume_dict:
                new_structures[new_key].volume = volume_dict[new_key]
        dvh.structures = new_structures

    # --- Lógica principal ---
    presc_names = list(presc.structures.keys())
    dvh_names = list(dvh_list_dummy[0].structures.keys())
    needs_volume = request_needed_volume(dvh_list_dummy, presc)

    replacement_dict = {}
    volume_dict = {}

    any_name_mismatch = any(name not in dvh_names for name in presc_names)
    any_volume_needed = len(needs_volume) > 0

    if any_name_mismatch or any_volume_needed:
        replacement_dict, volume_dict = launch_gui(presc_names, dvh_names, needs_volume)

    for dvh in dvh_list_dummy:
        apply_corrections(dvh, replacement_dict, volume_dict)


    # --- FLUJO PRINCIPAL ---
    dvh = dvh_list_dummy[0]
    dvh_names = list(dvh.structures.keys())
    presc_names = list(presc.structures.keys())

    replacement_dict = {}
    volume_dict = {}

    needs_volume = request_needed_volume(dvh_list_dummy, presc)
    launch_gui(presc_names, dvh_names, needs_volume)
    apply_corrections(dvh, replacement_dict, volume_dict)

def request_needed_volume(dvh, presc):
        need_volume_types = ['V(D)>V_cc', 'V(D)<V_cc', 'D(V_cc)<D', 'Dmax']
        needing_volume = []

        # Paso 1: Detectar las estructuras que requieren volumen
        for label, constraints in presc.structures.items():
            for constraint in constraints:
                if constraint.type in need_volume_types:
                    needing_volume.append(label)
                    break

        # Paso 2: Filtrar estructuras que ya tienen volume distinto de 0
        filtered = []
        dvh_structures = dvh.structures
        for label in needing_volume:
            if label in dvh_structures:
                vol = dvh_structures[label].volume
                if vol is None or vol == 0:
                    filtered.append(label)
            else:
                filtered.append(label)  # Si no está en DVH, igual lo necesita

        return list(set(filtered))

def dose_police_in_action(dvh_list_dummy: List, presc: Prescription):
    # CHEQUEANDO CONSTRAINTS
    for p_name in list(presc.structures.keys()):
        # print(f'{p_name} constraints:')
        for constraint in presc.structures[p_name]:
            if p_name in ['PTV_BOOST_TOTAL']: continue  # PTV_BOOST_TOTAL no tiene constraints
            constraint.verify(dvh_list_dummy[0].structures[p_name])

            # if not constraint.ACCEPTABLE_LV_AVAILABLE:
            #     if constraint.VERIFIED_IDEAL[0]:
            #         print(colored(f"    PASA IDEAL: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}",'green'))
            #     else:
            #         print(colored(f"    NO PASA: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}",'red'))
            # else:
            #     if constraint.VERIFIED_IDEAL[0]:
            #         print(colored(f"    PASA IDEAL: {constraint.type}: {constraint.ideal_dose} {constraint.ideal_volume} -> {constraint.ideal_dose} {constraint.VERIFIED_IDEAL[1]}",'green'))
            #     elif constraint.VERIFIED_ACCEPTABLE[0]:
            #         print(colored(f"    PASA ACEPTABLE: {constraint.type}: {constraint.acceptable_dose} {constraint.acceptable_volume} -> {constraint.acceptable_dose} {constraint.VERIFIED_ACCEPTABLE[1]}",'yellow'))
            #     else:
            #         print(colored(f"    NO PASA: {constraint.type}: {constraint.acceptable_dose} {constraint.acceptable_volume} -> {constraint.acceptable_dose} {constraint.VERIFIED_ACCEPTABLE[1]}",'red'))
