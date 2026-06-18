
import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# ============================================================
# CONFIGURACIÓN
# ============================================================
st.set_page_config(
    page_title="Confirmación de Asistencia",
    page_icon="✅",
    layout="centered"
)

ARCHIVO_INVITADOS = "nombres de los telefonos.xlsx"
COLECCION_CONFIRMACIONES = "confirmaciones_sonora_con_todo"

# ============================================================
# ESTILO
# ============================================================
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

# ============================================================
# FIREBASE
# ============================================================
@st.cache_resource
def conectar_firebase():
    try:
        if not firebase_admin._apps:
            if "firebase" not in st.secrets:
                return None, "No se encontró [firebase] en Secrets."

            fb = dict(st.secrets["firebase"])
            cred = credentials.Certificate(fb)
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        return db, None

    except Exception as e:
        return None, str(e)


db, error_firebase = conectar_firebase()


def firebase_conectado():
    return db is not None


# ============================================================
# DATOS
# ============================================================
@st.cache_data(ttl=300)
def cargar_invitados():
    if not os.path.exists(ARCHIVO_INVITADOS):
        return pd.DataFrame()

    df = pd.read_excel(ARCHIVO_INVITADOS, header=None)
    df = df.dropna(how="all")

    # El Excel puede venir con 4 columnas:
    # telefono, nombre, puesto, area
    # o con 6 columnas:
    # telefono, nombre, apellido_paterno, apellido_materno, puesto, area
    if df.shape[1] == 4:
        df = df.iloc[:, :4]
        df.columns = ["telefono", "nombre", "puesto", "area"]
        df["apellido_paterno"] = ""
        df["apellido_materno"] = ""

    elif df.shape[1] >= 6:
        df = df.iloc[:, :6]
        df.columns = ["telefono", "nombre", "apellido_paterno", "apellido_materno", "puesto", "area"]

    else:
        st.error("El Excel debe tener 4 columnas o 6 columnas.")
        st.stop()

    # Reordenar columnas para que el resto del sistema funcione igual
    df = df[["telefono", "nombre", "apellido_paterno", "apellido_materno", "puesto", "area"]]

    df["telefono"] = (
        df["telefono"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("-", "", regex=False)
        .str.strip()
    )

    df["nombre_completo"] = (
        df["nombre"].astype(str).str.strip() + " " +
        df["apellido_paterno"].astype(str).str.strip() + " " +
        df["apellido_materno"].astype(str).str.strip()
    ).str.replace("  ", " ", regex=False).str.strip().str.upper()

    df["puesto"] = df["puesto"].astype(str).str.strip().str.upper()
    df["area"] = df["area"].astype(str).str.strip().str.upper()

    return df


def guardar_confirmacion_firestore(datos):
    if not firebase_conectado():
        st.error("Firebase no está conectado. No se pudo guardar.")
        return False

    try:
        telefono = str(datos["telefono"]).replace(" ", "").replace(".0", "").strip()
        db.collection(COLECCION_CONFIRMACIONES).document(telefono).set(datos, merge=True)
        return True
    except Exception as e:
        st.error(f"No se pudo guardar en Firebase: {e}")
        return False


@st.cache_data(ttl=30)
def leer_confirmaciones_firestore():
    if not firebase_conectado():
        return pd.DataFrame()

    try:
        docs = db.collection(COLECCION_CONFIRMACIONES).stream(timeout=20)
        registros = []
        for doc in docs:
            d = doc.to_dict()
            d["firebase_id"] = doc.id
            registros.append(d)

        return pd.DataFrame(registros)
    except Exception as e:
        st.warning(f"No se pudieron leer confirmaciones: {e}")
        return pd.DataFrame()


def descargar_excel(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return output


# ============================================================
# INTERFAZ
# ============================================================
df = cargar_invitados()

st.markdown("<h1 style='text-align:center;'>✅ Confirmación de Asistencia</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Evento Sonora con Todo</p>", unsafe_allow_html=True)

if firebase_conectado():
    st.sidebar.success("Firebase conectado")
else:
    st.sidebar.error("Firebase no conectado")
    with st.sidebar.expander("Ver error"):
        st.write(error_firebase)

with st.sidebar.expander("Panel administrador"):
    clave_admin = st.text_input("Contraseña admin", type="password")

    if clave_admin == "1234":
        if st.button("🔄 Actualizar respuestas"):
            leer_confirmaciones_firestore.clear()
            st.rerun()

        respuestas = leer_confirmaciones_firestore()

        if respuestas.empty:
            st.info("Todavía no hay confirmaciones.")
        else:
            total_confirmaciones = len(respuestas)
            total_si = len(respuestas[respuestas["asistencia"] == "Sí asistiré"]) if "asistencia" in respuestas.columns else 0
            total_no = len(respuestas[respuestas["asistencia"] == "No asistiré"]) if "asistencia" in respuestas.columns else 0
            total_acompanantes = int(pd.to_numeric(respuestas.get("acompanantes", 0), errors="coerce").fillna(0).sum())
            total_personas = int(pd.to_numeric(respuestas.get("total_personas", 0), errors="coerce").fillna(0).sum())

            st.metric("Confirmaciones", total_confirmaciones)
            st.metric("Sí asistirán", total_si)
            st.metric("No asistirán", total_no)
            st.metric("Acompañantes", total_acompanantes)
            st.metric("Total personas", total_personas)

            st.download_button(
                "📥 Descargar Excel",
                data=descargar_excel(respuestas),
                file_name="confirmaciones_sonora_con_todo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if df.empty:
    st.error("No se encontró el archivo de invitados. Sube el Excel con el nombre exacto: nombres de los telefonos.xlsx")
    st.stop()

query_params = st.query_params
tel_url = query_params.get("tel", "")

if isinstance(tel_url, list):
    tel_url = tel_url[0]

tel_url = str(tel_url).replace(".0", "").replace(" ", "").strip()

if not tel_url:
    st.warning("Falta el teléfono en la liga.")
    st.info("Ejemplo: https://TU-APP.streamlit.app/?tel=6624809155")
    tel_url = st.text_input("Para prueba, escribe teléfono")

if tel_url:
    invitado = df[df["telefono"] == tel_url]

    if invitado.empty:
        st.error("No encontramos este teléfono en la lista de invitados.")
        st.write(f"Teléfono recibido: {tel_url}")
    else:
        persona = invitado.iloc[0]

        # Revisar si ya confirmó
        confirmacion_previa = None
        if firebase_conectado():
            try:
                doc = db.collection(COLECCION_CONFIRMACIONES).document(str(persona["telefono"])).get()
                if doc.exists:
                    confirmacion_previa = doc.to_dict()
            except Exception:
                confirmacion_previa = None

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Datos del invitado")

        st.write(f"**Nombre:** {persona['nombre_completo']}")
        st.write(f"**Teléfono:** {persona['telefono']}")
        st.write(f"**Puesto:** {persona['puesto']}")
        st.write(f"**Área:** {persona['area']}")

        if confirmacion_previa:
            st.info(
                f"Ya existe una confirmación registrada: "
                f"{confirmacion_previa.get('asistencia', '')} | "
                f"Acompañantes: {confirmacion_previa.get('acompanantes', 0)}"
            )

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
                "telefono": str(persona["telefono"]),
                "nombre_completo": str(persona["nombre_completo"]),
                "puesto": str(persona["puesto"]),
                "area": str(persona["area"]),
                "asistencia": asistencia,
                "acompanantes": int(acompanantes),
                "total_personas": int(total_personas),
                "observaciones": observaciones
            }

            ok = guardar_confirmacion_firestore(datos)

            if ok:
                leer_confirmaciones_firestore.clear()
                st.success("¡Gracias! Su confirmación fue registrada correctamente.")

        st.markdown("</div>", unsafe_allow_html=True)
