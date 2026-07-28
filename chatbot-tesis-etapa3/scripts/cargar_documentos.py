# Script de INGESTA: carga documentos a la base vectorial. Se corre A MANO.
'''
QUE HACE:
Lee los archivos de data/raw/ (PDF, TXT, MD), los corta en chunks, los embebe con OpenAI
y los guarda en ChromaDB. Despues de correrlo, el bot puede responder sobre ese contenido.

CUANDO LO CORRES:
- La primera vez que cargas documentos.
- Cada vez que AGREGAS, CAMBIAS o BORRAS un documento de data/raw/.
NO corre solo: vos decidis cuando actualizar la base de conocimiento.

COMO SE USA:
    cd chatbot-tesis-etapa3
    .\venv\Scripts\activate
    python -m scripts.cargar_documentos              # agrega/actualiza
    python -m scripts.cargar_documentos --reset      # borra todo y recarga desde cero

POR QUE UN SCRIPT APARTE (igual que crear_tablas.py):
- Embeber documentos cuesta plata y tiempo; no queres hacerlo en cada request.
- Lo haces una vez, queda guardado en disco, y el bot solo LEE de ahi.
'''


# Importacion de modulos
'''
sys: para leer argumentos de linea de comandos (--reset).
pathlib.Path: forma moderna y comoda de recorrer carpetas y archivos.
pypdf.PdfReader: para extraer texto de PDFs.
config: rutas y parametros.
chatbot.embeddings / vector_db: para embeber y guardar.
'''
import sys
from pathlib import Path
from pypdf import PdfReader
import config
from chatbot import embeddings
from chatbot import vector_db


# Carpeta donde estan los documentos fuente.
CARPETA_DOCUMENTOS = Path("data/raw")

# Parametros del troceo (chunking). Estan en "palabras" para que sea intuitivo.
'''
TAMANO_CHUNK: cuantas palabras tiene cada fragmento (~500 es estandar para FAQ).
SOLAPAMIENTO: cuantas palabras se repiten entre un chunk y el siguiente.
  El solapamiento evita "cortar" una idea justo en el borde entre dos chunks.
  Ej: si una respuesta esta partida entre el final de un chunk y el inicio del otro,
      el solapamiento garantiza que quede completa en al menos uno.
'''
TAMANO_CHUNK = 500
SOLAPAMIENTO = 50


def leer_texto_de_archivo(ruta):
    '''
    Extrae el texto de un archivo segun su extension.

    Soporta:
        .pdf  -> usa pypdf para extraer el texto de cada pagina.
        .txt / .md -> lee el contenido directo.

    Parametros:
        ruta: objeto Path al archivo.

    Devuelve:
        string con todo el texto del archivo (o "" si no se pudo leer / extension no soportada).
    '''
    extension = ruta.suffix.lower()

    if extension == ".pdf":
        # PdfReader abre el PDF; recorremos las paginas y concatenamos su texto.
        lector = PdfReader(str(ruta))
        paginas = [pagina.extract_text() or "" for pagina in lector.pages]
        return "\n".join(paginas)

    elif extension in (".txt", ".md"):
        # encoding="utf-8" para soportar acentos y ñ sin romperse.
        return ruta.read_text(encoding="utf-8")

    else:
        # Extension no soportada: avisamos y devolvemos vacio para saltarla.
        print(f"  [SKIP] Extension no soportada: {ruta.name}")
        return ""


def trocear(texto):
    '''
    Corta un texto largo en chunks de ~TAMANO_CHUNK palabras con SOLAPAMIENTO.

    Trabajamos a nivel de palabras (split por espacios). Es simple y funciona bien
    para documentos academicos. (Existen estrategias mas finas por oraciones/tokens,
    pero esta es clara y suficiente para la tesis.)

    Parametros:
        texto: string completo del documento.

    Devuelve:
        lista de strings (los chunks).
    '''
    # Separamos en palabras y descartamos espacios vacios.
    palabras = texto.split()

    if not palabras:
        return []

    chunks = []
    inicio = 0

    # Avanzamos de a (TAMANO_CHUNK - SOLAPAMIENTO) palabras: ese "paso" mas chico
    # que el tamano es lo que produce el solapamiento entre chunks consecutivos.
    paso = TAMANO_CHUNK - SOLAPAMIENTO

    while inicio < len(palabras):
        # Tomamos una ventana de TAMANO_CHUNK palabras desde "inicio".
        fin = inicio + TAMANO_CHUNK
        ventana = palabras[inicio:fin]
        chunks.append(" ".join(ventana))
        # Movemos el inicio para el proximo chunk.
        inicio += paso

    return chunks


def main():
    '''
    Flujo completo de la ingesta:
    1) (opcional) Vaciar la coleccion si se pasa --reset.
    2) Recorrer data/raw/.
    3) Por cada archivo: extraer texto -> trocear -> embeber -> guardar.
    4) Reportar cuantos chunks quedaron.
    '''
    # 1) Si pasaron --reset, borramos todo lo anterior para recargar desde cero.
    if "--reset" in sys.argv:
        print("[INGESTA] --reset: vaciando la coleccion vectorial...")
        vector_db.vaciar()

    # Validamos que la carpeta exista.
    if not CARPETA_DOCUMENTOS.exists():
        print(f"[INGESTA] No existe la carpeta {CARPETA_DOCUMENTOS}. Crea la carpeta y pone documentos.")
        return

    # 2) Listamos los archivos (ignoramos .gitkeep y subcarpetas).
    archivos = [a for a in CARPETA_DOCUMENTOS.iterdir() if a.is_file() and a.name != ".gitkeep"]

    if not archivos:
        print(f"[INGESTA] No hay documentos en {CARPETA_DOCUMENTOS}. Agrega PDFs/TXT/MD y volve a correr.")
        return

    total_chunks = 0

    # 3) Procesamos archivo por archivo.
    for archivo in archivos:
        print(f"[INGESTA] Procesando: {archivo.name}")

        texto = leer_texto_de_archivo(archivo)
        if not texto.strip():
            print(f"  [SKIP] Sin texto extraible: {archivo.name}")
            continue

        # Troceamos el documento.
        fragmentos = trocear(texto)
        print(f"  -> {len(fragmentos)} chunks")

        if not fragmentos:
            continue

        # Embebemos todos los chunks de este archivo en un solo lote (mas rapido/barato).
        vectores = embeddings.embeber_lote(fragmentos)

        # Armamos los datos que espera vector_db.guardar_chunks.
        # id unico por chunk: "nombrearchivo-indice" (asi re-cargar ACTUALIZA, no duplica).
        ids = [f"{archivo.name}-{i}" for i in range(len(fragmentos))]
        metadatos = [{"fuente": archivo.name} for _ in fragmentos]

        # Guardamos en ChromaDB.
        vector_db.guardar_chunks(
            ids=ids,
            textos=fragmentos,
            vectores=vectores,
            metadatos=metadatos,
        )

        total_chunks += len(fragmentos)

    # 4) Reporte final.
    print(f"[INGESTA] Listo. Chunks de esta corrida: {total_chunks}.")
    print(f"[INGESTA] Total de chunks en la base vectorial: {vector_db.contar()}.")


if __name__ == "__main__":
    main()
