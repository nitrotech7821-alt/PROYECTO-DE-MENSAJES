
import pandas as pd
import streamlit as st
from datetime import datetime
from io import BytesIO
import os

st.set_page_config(
    page_title="Confirmación de Asistencia",
    page_icon="✅",
    layout="centered"
)

ARCHIVO_INVITADOS = "nombres de los telefonos.xlsx"
ARCHIVO_RESPUESTAS = "confirmaciones_asistencia.xlsx"

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #EEF8F5 0%, #FFF7E7 55%, #FDE0CF 100%);
}
.card {
    background: white;
    padding: 25px;
    border-radius: 18px;
    box-shadow: 0px 5px 18px rgba(0,0,0,0.12);
    border-left: 7px solid #087B75;
}
h1, h2, h3 {
    color: #087B75;
}
.stButton > button {
    background: linear-gradient(90deg, #E94E1B, #F2B233);
    color: white;
    font-weight: bold;
    border-radius: 12px;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)


def cargar_invitados():
    if not os.path.exists(ARCHIVO_INVITADOS):
        return pd.DataFrame()

    df = pd.read_excel(ARCHIVO_INVITADOS, header=None)
    df = df.iloc[:, :6]
    df.columns = ["telefono", "nombre", "apellido_paterno", "apellido_materno", "puesto", "area"]

    df["telefono"] = (
        df["telefono"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.strip()
    )

    df["nombre_completo"] = (
        df["nombre"].astype(str).str.strip() + " " +
        df["apellido_paterno"].astype(str).str.strip() + " " +
        df["apellido_materno"].astype(str).str.strip()
    ).str.upper()

    return df


def guardar_respuesta(datos):
    if os.path.exists(ARCHIVO_RESPUESTAS):
        df_resp = pd.read_excel(ARCHIVO_RESPUESTAS)
    else:
        df_resp = pd.DataFrame()

    nuevo = pd.DataFrame([datos])

    if not df_resp.empty and "telefono" in df_resp.columns:
        df_resp = df_resp[df_resp["telefono"].astype(str) != str(datos["telefono"])]

    df_final = pd.concat([df_resp, nuevo], ignore_index=True)
    df_final.to_excel(ARCHIVO_RESPUESTAS, index=False)


def descargar_excel(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return output


df = cargar_invitados()

st.markdown("<h1 style='text-align:center;'>✅ Confirmación de Asistencia</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Evento Sonora con Todo</p>", unsafe_allow_html=True)

query_params = st.query_params
tel_url = query_params.get("tel", "")

if isinstance(tel_url, list):
    tel_url = tel_url[0]

tel_url = str(tel_url).replace(".0", "").replace(" ", "").strip()

if df.empty:
    st.error("No se encontró el archivo de invitados. Sube el Excel con el nombre exacto: nombres de los telefonos.xlsx")
    st.stop()

if not tel_url:
    st.warning("Falta el teléfono en la liga.")
    st.info("Ejemplo: ?tel=6624809155")
    tel_url = st.text_input("Para prueba, escribe teléfono")

if tel_url:
    invitado = df[df["telefono"] == tel_url]

    if invitado.empty:
        st.error("No encontramos este teléfono en la lista de invitados.")
        st.write(f"Teléfono recibido: {tel_url}")
    else:
        persona = invitado.iloc[0]

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Datos del invitado")

        st.write(f"**Nombre:** {persona['nombre_completo']}")
        st.write(f"**Teléfono:** {persona['telefono']}")
        st.write(f"**Puesto:** {persona['puesto']}")
        st.write(f"**Área:** {persona['area']}")

        st.markdown("---")

        asistencia = st.radio(
            "¿Asistirá al evento?",
            ["Sí asistiré", "No asistiré"]
        )

        acompanantes = 0
        if asistencia == "Sí asistiré":
            acompanantes = st.number_input(
                "¿Cuántos acompañantes llevará?",
                min_value=0,
                max_value=20,
                value=0,
                step=1
            )

        observaciones = st.text_area("Observaciones opcionales")

        if st.button("✅ Confirmar asistencia"):
            total_personas = 1 + int(acompanantes) if asistencia == "Sí asistiré" else 0

            datos = {
                "fecha_confirmacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "telefono": persona["telefono"],
                "nombre_completo": persona["nombre_completo"],
                "puesto": persona["puesto"],
                "area": persona["area"],
                "asistencia": asistencia,
                "acompanantes": int(acompanantes),
                "total_personas": total_personas,
                "observaciones": observaciones
            }

            guardar_respuesta(datos)
            st.success("¡Gracias! Su confirmación fue registrada correctamente.")

        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

with st.expander("Panel de administración"):
    clave = st.text_input("Contraseña admin", type="password")

    if clave == "1234":
        if os.path.exists(ARCHIVO_RESPUESTAS):
            respuestas = pd.read_excel(ARCHIVO_RESPUESTAS)

            st.metric("Confirmaciones registradas", len(respuestas))
            st.metric("Total personas esperadas", int(respuestas["total_personas"].sum()))

            st.dataframe(respuestas, use_container_width=True)

            st.download_button(
                "📥 Descargar confirmaciones Excel",
                data=descargar_excel(respuestas),
                file_name="confirmaciones_asistencia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Todavía no hay confirmaciones.")
    elif clave:
        st.error("Contraseña incorrecta.")
