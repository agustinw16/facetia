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


def tiene_formato_preguntas(texto):
    '''
    Devuelve True si el texto usa el formato "## pregunta" (el de
    facet_info_general.txt: cada bloque de preguntas y respuesta arranca con
    "## "). Las paginas scrapeadas de la web y los PDF no usan este formato.
    '''
    return any(linea.startswith("## ") for linea in texto.splitlines())


def trocear_por_bloques(texto):
    '''
    Corta el texto en UN CHUNK POR CADA BLOQUE "## pregunta", sin importar
    cuantas palabras tenga. Se usa en vez de trocear() para archivos con
    formato de preguntas y respuesta (ver facet_info_general.txt): ahi, cortar
    por cantidad de palabras mezclaria varios temas sin relacion en un mismo
    chunk (ej: horario de atencion + redes sociales + ingreso), diluyendo la
    busqueda por significado. Cortando por bloque, cada pregunta queda como su
    propia unidad de busqueda, tal como lo pensaste al escribir el archivo.

    Todo lo que esta ANTES del primer "## " (las instrucciones de
    mantenimiento, el indice, los encabezados de seccion) se descarta: es para
    quien edita el archivo, no es informacion para responderle a un estudiante.

    Parametros:
        texto: string completo del documento.

    Devuelve:
        lista de strings (un bloque por pregunta).
    '''
    bloques = []
    bloque_actual = []

    for linea in texto.splitlines():
        if linea.startswith("## "):
            # Encontramos una pregunta nueva: cerramos el bloque anterior (si habia)
            # y arrancamos uno nuevo con esta linea.
            if bloque_actual:
                bloques.append("\n".join(bloque_actual).strip())
            bloque_actual = [linea]
        elif bloque_actual:
            # Solo acumulamos lineas despues de encontrar el primer "## ":
            # lo anterior (instrucciones, indice) queda afuera.
            bloque_actual.append(linea)

    if bloque_actual:
        bloques.append("\n".join(bloque_actual).strip())

    # Por si quedo algun bloque vacio (no deberia pasar, pero por las dudas).
    return [b for b in bloques if b]


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

        # Troceamos el documento. Si tiene formato "## pregunta" (ej:
        # facet_info_general.txt), un chunk por bloque. Si no (paginas web, PDF),
        # por cantidad de palabras, como siempre.
        if tiene_formato_preguntas(texto):
            fragmentos = trocear_por_bloques(texto)
            print(f"  -> {len(fragmentos)} chunks (por bloque de pregunta)")
        else:
            fragmentos = trocear(texto)
            print(f"  -> {len(fragmentos)} chunks (por cantidad de palabras)")

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
