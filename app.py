import streamlit as st
import pandas as pd
import os
import base64

# --- Configuración de la página ---
st.set_page_config(page_title="Dose Police", layout="wide")

# --- Función para la marca de agua ---
def add_watermark(image_path):
    with open(image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode()

    css = f"""
    <style>
    .watermark {{
        position: fixed;
        top: 130%;
        left: 65%;
        transform: translate(-50%, -50%);
        opacity: 0.2;
        z-index: 0;
        pointer-events: none;
    }}
    </style>
    <img class="watermark" src="data:image/png;base64,{encoded}" width="1500"/>
    """
    st.markdown(css, unsafe_allow_html=True)

# Agregar la marca de agua al fondo
add_watermark("./images/dvh_watermark.png")

# --- Barra lateral ---
st.sidebar.image("./images/logo_intecnus.png", width=230)

patient_id = st.sidebar.text_input("Filtrar por ID de Paciente")

TXT_DIR = "./dvhs"
def list_txt_files(directory, patient_filter=""):
    files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    if patient_filter:
        files = [f for f in files if patient_filter.lower() in f.lower()]
    return files

txt_files = list_txt_files(TXT_DIR, patient_id)

st.sidebar.subheader("Archivos TXT")
for file in txt_files:
    st.sidebar.button(file, use_container_width=True)

# --- Título con logo de policía ---
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image("./images/logo_policia.png", width=90)
with col_title:
    st.title("Dose Police: Verificador de Constraints de Radioterapia by RL.")

# --- Menú de prescripción ---
prescription_template = st.selectbox(
    "Template de prescripción",
    ["Prostata", "Mama", "Cabeza y Cuello", "Pelvis"]
)

# --- Layout inferior ---
left_col, main_col = st.columns([1,3])

structures_data = [
    {"Estructura": "Próstata", "Constraint": "V70Gy < 15%", "Resultado": "Cumple"},
    {"Estructura": "Recto", "Constraint": "V60Gy < 35%", "Resultado": "No Cumple"},
    {"Estructura": "Vejiga", "Constraint": "V65Gy < 25%", "Resultado": "Cumple"}
]
df_structures = pd.DataFrame(structures_data)

with main_col:
    st.subheader("Verificación de Constraints por Estructura")
    st.dataframe(df_structures, use_container_width=True)

# --- Footer ---
st.markdown("---")
st.markdown("Aplicación desarrollada por Roy Lápera")
