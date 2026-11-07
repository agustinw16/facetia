# Script de CONSULTA: muestra que hay guardado adentro de la base vectorial (ChromaDB).
# La "r" antes de las comillas evita que Python interprete las "\" de las rutas de Windows.
r'''
QUE HACE:
Abre la base vectorial que genera cargar_documentos.py y muestra, por consola:
- Cuantos fragmentos (chunks) hay guardados y de que archivos salieron.
- Cada fragmento: su ID, su fuente, un pedazo del texto y los primeros numeros de su vector.
- Si la base esta DESACTUALIZADA respecto de los archivos de data/raw/.
Opcionalmente, simula una pregunta y muestra que fragmentos encontraria el bot.

NO MODIFICA NADA: solo lee. Se puede correr las veces que quieras.

COMO SE USA:
    cd chatbot-tesis-etapa3
    .\venv\Scripts\activate
    python -m scripts.ver_base_vectorial                          # resumen + fragmentos (texto recortado)
    python -m scripts.ver_base_vectorial --completo               # muestra el texto entero de cada fragmento
    python -m scripts.ver_base_vectorial --buscar "cuando me inscribo"   # simula una busqueda del bot

COSTO:
- Sin --buscar: USD 0 (solo lee el disco).
- Con --buscar: convierte la pregunta en vector con OpenAI (una fraccion de centavo).
'''


# Importacion de modulos
'''
sys: para leer los argumentos de linea de comandos (--completo, --buscar).
pathlib.Path: para listar los archivos de data/raw/ y compararlos con la base.
chromadb: la libreria de la base vectorial. La usamos directo (y no via vector_db.py)
  porque este script es una herramienta de INSPECCION: necesita leer todo el contenido,
  cosa que el bot nunca hace.
config: ruta de la base y nombre de la coleccion (los mismos que usa el bot).
'''
import sys
from pathlib import Path
import chromadb
import config


# Carpeta de los documentos fuente (la misma que lee cargar_documentos.py).
CARPETA_DOCUMENTOS = Path("data/raw")

# Extensiones que el script de ingesta sabe leer.
EXTENSIONES_SOPORTADAS = (".pdf", ".txt", ".md")

# Cuantos caracteres de texto mostrar por fragmento cuando NO se pide --completo.
LARGO_VISTA_PREVIA = 300

# Cuantos numeros del vector mostrar (el vector completo tiene 1536: ilegible por consola).
NUMEROS_VECTOR_A_MOSTRAR = 8


def linea(caracter="=", largo=70):
    '''
    Imprime una linea separadora para que la salida por consola sea mas facil de leer.
    '''
    print(caracter * largo)


def abrir_coleccion():
    '''
    Abre la coleccion de ChromaDB en modo lectura.

    Usamos get_collection (y NO get_or_create_collection como vector_db.py)
    porque si la base no existe queremos AVISAR, no crear una vacia.

    Devuelve:
        la coleccion, o None si todavia no se cargo ningun documento.
    '''
    # PersistentClient abre la carpeta donde Chroma guarda todo (data/processed/chroma/).
    cliente = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    try:
        return cliente.get_collection(name=config.CHROMA_COLLECTION)
    except Exception:
        # Chroma lanza una excepcion si la coleccion no existe.
        return None


def mostrar_resumen(datos):
    '''
    Muestra cuantos fragmentos hay, de que archivos salieron, y si la base
    esta desactualizada respecto de data/raw/.

    Parametros:
        datos: dict devuelto por coleccion.get() con ids, documents, metadatas y embeddings.
    '''
    # Contamos cuantos fragmentos aporta cada archivo fuente.
    fragmentos_por_fuente = {}
    for metadato in datos["metadatas"]:
        fuente = metadato.get("fuente", "(sin fuente)")
        fragmentos_por_fuente[fuente] = fragmentos_por_fuente.get(fuente, 0) + 1

    # Los vectores tienen todos el mismo largo; tomamos el del primero.
    dimensiones = len(datos["embeddings"][0]) if len(datos["ids"]) > 0 else 0

    linea()
    print("RESUMEN DE LA BASE VECTORIAL")
    linea()
    print(f"Ubicacion:            {config.CHROMA_DB_PATH}")
    print(f"Coleccion:            {config.CHROMA_COLLECTION}")
    print(f"Fragmentos guardados: {len(datos['ids'])}")
    print(f"Numeros por vector:   {dimensiones}")
    print("\nArchivos de origen:")
    for fuente, cantidad in sorted(fragmentos_por_fuente.items()):
        print(f"  - {fuente}: {cantidad} fragmento(s)")

    # Comparamos lo que hay en data/raw/ con lo que hay en la base.
    '''
    La base NO se actualiza sola: si editas o agregas un archivo en data/raw/
    hay que volver a correr cargar_documentos.py. Aca detectamos los casos tipicos:
    - Archivos en data/raw/ que no estan en la base (falta cargarlos).
    - Fuentes en la base que ya no estan en data/raw/ (quedaron de cargas viejas).
    No detecta si un archivo fue EDITADO: para eso, ante la duda, recargar con --reset.
    '''
    en_disco = {
        archivo.name
        for archivo in CARPETA_DOCUMENTOS.iterdir()
        if archivo.suffix.lower() in EXTENSIONES_SOPORTADAS
    } if CARPETA_DOCUMENTOS.exists() else set()
    en_base = set(fragmentos_por_fuente.keys())

    faltan_cargar = en_disco - en_base
    sobran_en_base = en_base - en_disco

    if faltan_cargar or sobran_en_base:
        print("\nATENCION: la base esta DESACTUALIZADA respecto de data/raw/")
        for nombre in sorted(faltan_cargar):
            print(f"  - {nombre}: esta en data/raw/ pero NO en la base")
        for nombre in sorted(sobran_en_base):
            print(f"  - {nombre}: esta en la base pero ya NO en data/raw/")
        print("  Para actualizarla: python -m scripts.cargar_documentos --reset")
    else:
        print("\nLa base coincide con los archivos de data/raw/.")


def mostrar_fragmentos(datos, completo):
    '''
    Muestra cada fragmento guardado: ID, fuente, texto y los primeros numeros de su vector.

    Parametros:
        datos: dict devuelto por coleccion.get().
        completo: True para mostrar el texto entero, False para una vista previa.
    '''
    linea()
    print("FRAGMENTOS GUARDADOS")
    linea()

    # zip recorre las 4 listas en paralelo: el fragmento i, su texto i, su metadato i y su vector i.
    for numero, (id_, texto, metadato, vector) in enumerate(
        zip(datos["ids"], datos["documents"], datos["metadatas"], datos["embeddings"]), start=1
    ):
        print(f"\n[{numero}] ID: {id_}")
        print(f"    Fuente: {metadato.get('fuente', '(sin fuente)')}")

        # Si no se pide --completo, recortamos el texto y reemplazamos saltos de linea
        # para que cada fragmento ocupe pocas lineas en la consola.
        if completo:
            print(f"    Texto:\n{texto}")
        else:
            vista = texto[:LARGO_VISTA_PREVIA].replace("\n", " ")
            puntos = "..." if len(texto) > LARGO_VISTA_PREVIA else ""
            print(f"    Texto ({len(texto)} caracteres): {vista}{puntos}")

        # Redondeamos a 4 decimales para que se lea; el vector real tiene 1536 numeros.
        primeros = [round(float(x), 4) for x in vector[:NUMEROS_VECTOR_A_MOSTRAR]]
        print(f"    Vector ({len(vector)} numeros): {primeros} ...")


def simular_busqueda(coleccion, pregunta):
    '''
    Hace lo mismo que el bot cuando recibe una pregunta: la convierte en vector
    y busca los fragmentos mas parecidos. Muestra cuales encontro y que tan parecidos son.

    Parametros:
        coleccion: la coleccion de ChromaDB ya abierta.
        pregunta: texto de la pregunta a simular.
    '''
    # Importamos aca (y no arriba) porque solo hace falta OpenAI si se pide --buscar.
    # Asi el modo de solo lectura funciona aunque no haya API key configurada.
    from chatbot import embeddings

    linea()
    print(f'SIMULACION DE BUSQUEDA: "{pregunta}"')
    linea()

    # 1) La pregunta se convierte en vector con el MISMO modelo que se uso para los documentos.
    vector_pregunta = embeddings.embeber_texto(pregunta)

    # 2) Chroma devuelve los RAG_TOP_K fragmentos mas cercanos (los mismos que recibiria el bot).
    resultado = coleccion.query(
        query_embeddings=[vector_pregunta],
        n_results=min(config.RAG_TOP_K, coleccion.count()),
        include=["documents", "metadatas", "distances"],
    )

    # 3) Mostramos cada resultado con su "similitud".
    '''
    Chroma devuelve una DISTANCIA coseno (0 = identico, mas alto = menos parecido).
    Para que se entienda mejor la convertimos en similitud: 1 - distancia.
    Ej: 0.85 = muy parecido en significado; 0.30 = poco relacionado.
    '''
    for posicion, (texto, metadato, distancia) in enumerate(
        zip(resultado["documents"][0], resultado["metadatas"][0], resultado["distances"][0]), start=1
    ):
        similitud = 1 - distancia
        vista = texto[:LARGO_VISTA_PREVIA].replace("\n", " ")
        print(f"\n#{posicion} | similitud: {similitud:.2f} | fuente: {metadato.get('fuente')}")
        print(f"    {vista}...")


def main():
    '''
    Punto de entrada: lee los argumentos, abre la base y muestra su contenido.
    '''
    # Argumentos de linea de comandos.
    completo = "--completo" in sys.argv
    pregunta = None
    if "--buscar" in sys.argv:
        indice = sys.argv.index("--buscar")
        # La pregunta es el argumento que viene despues de --buscar.
        if indice + 1 < len(sys.argv):
            pregunta = sys.argv[indice + 1]
        else:
            print('Falta la pregunta. Ejemplo: python -m scripts.ver_base_vectorial --buscar "horarios"')
            return

    coleccion = abrir_coleccion()
    if coleccion is None or coleccion.count() == 0:
        print("La base vectorial esta vacia o todavia no existe.")
        print("Primero carga los documentos: python -m scripts.cargar_documentos")
        return

    # get() sin filtros trae TODO. include indica que campos queremos recibir
    # (por defecto Chroma no devuelve los vectores, hay que pedirlos).
    datos = coleccion.get(include=["documents", "metadatas", "embeddings"])

    mostrar_resumen(datos)
    mostrar_fragmentos(datos, completo)

    if pregunta:
        simular_busqueda(coleccion, pregunta)

    linea()


if __name__ == "__main__":
    main()
