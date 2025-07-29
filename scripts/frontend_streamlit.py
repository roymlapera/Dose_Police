
import streamlit as st
import pandas as pd
from backend_module import DVH, Prescription, dose_police_in_action

# Título de la app
st.title("Verificador de Constraints - DVH + Prescripción")

# Subida de archivos
uploaded_dvh = st.file_uploader("📄 Subí el archivo DVH (.txt)", type="txt")
uploaded_constraints = st.file_uploader("📋 Subí el archivo de constraints (.xlsx)", type="xlsx")

# Selección de protocolo
protocol_name = st.text_input("📌 Nombre del protocolo (ej: PARARRECTAL)")

# Iniciar procesamiento si todos los inputs están completos
if uploaded_dvh and uploaded_constraints and protocol_name:
    # Guardar archivos temporales
    dvh_path = "temp_dvh.txt"
    with open(dvh_path, "wb") as f:
        f.write(uploaded_dvh.read())

    constraints_path = "temp_constraints.xlsx"
    with open(constraints_path, "wb") as f:
        f.write(uploaded_constraints.read())

    # Crear instancias de DVH y Prescription
    dvh = DVH(dvh_path)
    presc = Prescription(constraints_path, protocol_name)

    # Estructuras detectadas
    st.subheader("🧠 Asignación de volumen por estructura")
    volumes = {}
    for structure_name in dvh.structures:
        volume_input = st.number_input(f"Volumen (cc) para '{structure_name}'", min_value=0.0, step=1.0)
        dvh.structures[structure_name].volume_update(volume_input)

    # Verificación final
    if st.button("✅ Verificar restricciones"):
        st.info("Ejecutando análisis...")
        dose_police_in_action([dvh], presc)
        st.success("✔️ Análisis completado. Revisá los resultados en consola o PDF generado (si aplica).")
else:
    st.warning("🛑 Esperando que cargues todos los archivos y nombre del protocolo.")
