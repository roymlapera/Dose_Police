import streamlit as st
from typing import List
import os

# --- Asumo que estas clases y funciones vienen de tu backend_module ---
# Acá defino solo lo estrictamente necesario para que funcione integrado.

class Structure:
    def __init__(self, label, volume=None):
        self.label = label
        self.volume = volume or 0.0
        self.dose_axis = list(range(0, 10001, 100))  # Ejemplo dummy
        self.cumulated_percent_volume_axis = [100 - (i / 100) for i in self.dose_axis]  # Simple decay

    def volume_function(self, dose):
        return max(0.0, 100 - dose / 100)

    def dose_function(self, volume):
        return max(0.0, (100 - volume) * 100)

    def volume_update(self, volume):
        self.volume = volume

    @property
    def mean(self):
        return sum(self.dose_axis) / len(self.dose_axis)


class Constraint:
    def __init__(self, constraints_chart_line):
        self.structure_name, self.type, self.ideal_dose, self.ideal_volume, self.acceptable_dose, self.acceptable_volume = constraints_chart_line
        self.structure_name = self.structure_name.upper()
        self.VERIFIED_IDEAL = (False, 0.0)
        self.VERIFIED_ACCEPTABLE = (False, 0.0)
        self.ACCEPTABLE_LV_AVAILABLE = self.acceptable_dose != 'None'

    def _evaluate(self, structure, ref1, ref2):
        constraint_types = ['V(D)>V_%', 'V(D)>V_cc', 'V(D)<V_%', 'V(D)<V_cc', 'D(V_%)<D', 'D(V_cc)<D', 'Dmax', 'Dmedia']

        if self.type in constraint_types[:4]:
            is_superior = self.type in (constraint_types[2], constraint_types[3])
            abs_volume = self.type in (constraint_types[1], constraint_types[3])

            ref_dose = float(ref1)
            ref_vol = float(ref2)
            result = structure.volume_function(ref_dose)
            result = result * structure.volume / 100.0 if abs_volume else result
            PASS = result <= ref_vol if is_superior else result >= ref_vol
            return (PASS, round(result, 1))

        elif self.type in constraint_types[4:6]:
            abs_volume = self.type == constraint_types[5]
            ref_vol = float(ref1)
            ref_vol = ref_vol * 100.0 / structure.volume if abs_volume else ref_vol
            ref_dose = float(ref2)
            result = structure.dose_function(ref_vol)
            PASS = result <= ref_dose
            return (PASS, round(result, 1))

        elif self.type in constraint_types[6:]:
            dmax = self.type == constraint_types[6]
            dmed = self.type == constraint_types[7]
            ref_dose = float(ref1)
            result = structure.mean if dmed else structure.dose_function(2.0)
            PASS = result <= ref_dose
            return (PASS, round(result, 1))

        else:
            return (False, 'None')

    def verify(self, structure):
        self.VERIFIED_IDEAL = self._evaluate(structure, self.ideal_dose, self.ideal_volume)
        if not self.VERIFIED_IDEAL[0] and self.ACCEPTABLE_LV_AVAILABLE:
            self.VERIFIED_ACCEPTABLE = self._evaluate(structure, self.acceptable_dose, self.acceptable_volume)

class DVH:
    def __init__(self, file_path):
        # Aquí deberías reemplazar esta simulación por tu parser real
        # Para demo, simulo 3 estructuras
        self.structures = {
            "PTV": Structure("PTV", volume=800),
            "BLADDER": Structure("BLADDER", volume=150),
            "RECTUM": Structure("RECTUM", volume=120),
        }

class Prescription:
    def __init__(self, constraint_excel_filepath, presc_template_name):
        # Simulo algunas constraints para demo
        self.structures = {
            "PTV": [Constraint(["PTV", "D(V_cc)<D", 95, 0.03, 90, 0.03])],
            "BLADDER": [Constraint(["BLADDER", "V(D)<V_%", 65, 50, 70, 60])],
            "RECTUM": [Constraint(["RECTUM", "Dmax", 75, None, 80, None])],
        }

# --- Función para emparejar nombres y pedir volúmenes dentro de Streamlit ---
def match_strings_and_volume_entry_streamlit(dvh_list_dummy, presc):
    presc_names = list(presc.structures.keys())
    dvh_names = list(dvh_list_dummy[0].structures.keys())

    need_volume_types = ['V(D)>V_cc', 'V(D)<V_cc', 'D(V_cc)<D', 'Dmax']
    needs_volume = []
    for label, constraints in presc.structures.items():
        for constraint in constraints:
            if constraint.type in need_volume_types:
                needs_volume.append(label)
                break

    filtered_needs_volume = []
    dvh_structures = dvh_list_dummy[0].structures
    for label in needs_volume:
        if label in dvh_structures:
            vol = dvh_structures[label].volume
            if vol is None or vol == 0:
                filtered_needs_volume.append(label)
        else:
            filtered_needs_volume.append(label)

    st.subheader("Emparejamiento de estructuras y asignación de volúmenes")

    replacement_dict = {}
    volume_dict = {}

    for presc_name in presc_names:
        needs_rename = presc_name not in dvh_names
        needs_vol = presc_name in filtered_needs_volume

        cols = st.columns([2, 3, 2])
        with cols[0]:
            st.write(f"**{presc_name}**")
        with cols[1]:
            if needs_rename:
                replacement = st.selectbox(f"Asignar estructura DVH para {presc_name}", options=dvh_names, key=f"rename_{presc_name}")
            else:
                replacement = presc_name
                st.write(f"Asignado: {replacement}")
        with cols[2]:
            if needs_vol:
                vol = st.number_input(f"Volumen (cc) para {presc_name}", min_value=0.0, value=0.0, key=f"vol_{presc_name}")
            else:
                vol = dvh_structures.get(presc_name, Structure(presc_name, 0)).volume or 0.0
                st.write(f"Volumen: {vol}")

        replacement_dict[presc_name] = replacement
        volume_dict[presc_name] = vol

    # Aplicar cambios a las estructuras
    for dvh in dvh_list_dummy:
        new_structures = {}
        for old_key, structure in dvh.structures.items():
            matched_presc = next((k for k, v in replacement_dict.items() if v == old_key), None)
            new_key = matched_presc if matched_presc else old_key
            structure.label = new_key
            if new_key in volume_dict and volume_dict[new_key] is not None:
                structure.volume_update(volume_dict[new_key])
            new_structures[new_key] = structure
        dvh.structures = new_structures


# --- Función para ejecutar la verificación y mostrar resultados ---
def dose_police_in_action(dvh_list_dummy: List, presc: Prescription):
    # Primero se pide el emparejamiento y volúmenes en UI
    match_strings_and_volume_entry_streamlit(dvh_list_dummy, presc)

    st.subheader("Resultados de constraints")

    for p_name in list(presc.structures.keys()):
        for constraint in presc.structures[p_name]:
            structure = dvh_list_dummy[0].structures.get(p_name)
            if not structure:
                st.warning(f"Estructura {p_name} no encontrada en DVH")
                continue

            constraint.verify(structure)
            if not constraint.ACCEPTABLE_LV_AVAILABLE:
                if constraint.VERIFIED_IDEAL[0]:
                    st.success(f"{p_name}: PASA IDEAL {constraint.type} - Resultado: {constraint.VERIFIED_IDEAL[1]}")
                else:
                    st.error(f"{p_name}: NO PASA {constraint.type} - Resultado: {constraint.VERIFIED_IDEAL[1]}")
            else:
                if constraint.VERIFIED_IDEAL[0]:
                    st.success(f"{p_name}: PASA IDEAL {constraint.type} - Resultado: {constraint.VERIFIED_IDEAL[1]}")
                elif constraint.VERIFIED_ACCEPTABLE[0]:
                    st.warning(f"{p_name}: PASA ACEPTABLE {constraint.type} - Resultado: {constraint.VERIFIED_ACCEPTABLE[1]}")
                else:
                    st.error(f"{p_name}: NO PASA {constraint.type} - Resultado: {constraint.VERIFIED_ACCEPTABLE[1]}")



# --- Interfaz Streamlit principal ---

st.title("Verificador de Constraints - DVH + Prescripción")

uploaded_dvh = st.file_uploader("📄 Subí el archivo DVH (.txt)", type="txt")
uploaded_constraints = st.file_uploader("📋 Subí el archivo de constraints (.xlsx)", type="xlsx")
protocol_name = st.text_input("📌 Nombre del protocolo (ej: PARARRECTAL)")

if uploaded_dvh and uploaded_constraints and protocol_name:
    # Guardar archivos temporales
    dvh_path = "temp_dvh.txt"
    with open(dvh_path, "wb") as f:
        f.write(uploaded_dvh.read())

    constraints_path = "temp_constraints.xlsx"
    with open(constraints_path, "wb") as f:
        f.write(uploaded_constraints.read())

    # Crear instancias - reemplaza con tu implementación real
    dvh = DVH(dvh_path)
    presc = Prescription(constraints_path, protocol_name)

    dvh_list = [dvh]

    if st.button("✅ Verificar restricciones"):
        dose_police_in_action(dvh_list, presc)

else:
    st.warning("🛑 Esperando que cargues todos los archivos y nombre del protocolo.")
