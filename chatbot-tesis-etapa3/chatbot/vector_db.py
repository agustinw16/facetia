# Modulo de BASE DE DATOS VECTORIAL: guarda y busca chunks por similitud.
'''
QUE ES UNA VECTOR DB (repaso conceptual):
Es una base de datos especializada en buscar "los vectores mas parecidos a este otro".
Le damos el vector de la pregunta y nos devuelve los chunks cuyo significado mas se acerca.

Usamos ChromaDB en modo LOCAL/PERSISTENTE:
- "Local" = corre dentro de tu proceso Python, no necesita un servidor aparte.
- "Persistente" = guarda los datos en una carpeta del disco (config.CHROMA_DB_PATH),
  asi sobreviven a reinicios. (El otro modo, "in-memory", se borra al cerrar.)

Este archivo ENCAPSULA ChromaDB: el resto del codigo (rag.py, cargar_documentos.py)
no llama a ChromaDB directamente, llama a estas funciones. Si mañana cambiamos a Qdrant,
solo se toca este archivo (mismo principio que el repositorio.py de la BD relacional).

ACLARACION sobre los embeddings:
Nosotros generamos los embeddings con OpenAI (en embeddings.py) y se los PASAMOS a Chroma
ya calculados. Chroma NO los calcula por su cuenta. Asi controlamos que modelo se usa.
'''


# Importacion de modulos
'''
chromadb: la libreria de la base vectorial.
config: para leer la ruta de persistencia, el nombre de la coleccion y el top-K.
'''
import chromadb
import config


# Cliente y coleccion se crean UNA vez al importar el modulo (patron singleton simple).
'''
PersistentClient abre (o crea) la carpeta donde Chroma guarda todo en disco.
get_or_create_collection: si la coleccion ya existe la abre, si no la crea.
  - Es idempotente: correrlo muchas veces no rompe nada.
  - metadata {"hnsw:space": "cosine"} define que la similitud se mide por "distancia coseno",
    que es la metrica estandar y recomendada para embeddings de texto.
'''
_cliente = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
_coleccion = _cliente.get_or_create_collection(
    name=config.CHROMA_COLLECTION,
    metadata={"hnsw:space": "cosine"},
)


def guardar_chunks(ids, textos, vectores, metadatos):
    '''
    Guarda (o actualiza) una lista de chunks en la coleccion vectorial.

    Se usa en la INGESTA (cargar_documentos.py).

    Parametros (las 4 listas tienen que tener el MISMO largo y orden):
        ids: lista de identificadores unicos por chunk (ej: "reglamento.pdf-0", "reglamento.pdf-1").
             Sirve para que re-cargar el mismo documento ACTUALICE en vez de duplicar.
        textos: lista con el texto de cada chunk (Chroma lo guarda para devolverlo en la busqueda).
        vectores: lista con el embedding de cada chunk (ya calculado con OpenAI).
        metadatos: lista de dicts con info extra por chunk (ej: {"fuente": "reglamento.pdf"}).

    Devuelve:
        None.
    '''
    # upsert = "update or insert": si un id ya existe, lo reemplaza; si no, lo crea.
    # Asi podes volver a correr la ingesta sin generar duplicados.
    _coleccion.upsert(
        ids=ids,
        documents=textos,
        embeddings=vectores,
        metadatas=metadatos,
    )


def buscar_similares(vector_pregunta, k=None):
    '''
    Devuelve los K chunks mas parecidos (en significado) a la pregunta.

    Se usa en la CONSULTA (rag.py), cada vez que llega un mensaje.

    Parametros:
        vector_pregunta: el embedding de la pregunta del usuario (calculado con OpenAI).
        k: cuantos chunks devolver. Si es None, usa config.RAG_TOP_K.

    Devuelve:
        lista de dicts, cada uno con {"texto", "fuente", "distancia"}.
        - distancia: cuanto MENOR, mas parecido (0 = identico). Util para filtrar/ordenar.
        Si la coleccion esta vacia, devuelve lista vacia.
    '''
    if k is None:
        k = config.RAG_TOP_K

    # Si no hay nada cargado todavia, evitamos el query (devolveria vacio igual).
    if _coleccion.count() == 0:
        return []

    # query recibe una LISTA de vectores (podriamos buscar varias preguntas a la vez);
    # nosotros mandamos una sola, dentro de una lista.
    resultado = _coleccion.query(
        query_embeddings=[vector_pregunta],
        n_results=k,
    )

    # ChromaDB devuelve los resultados en listas anidadas (una por cada query).
    # Como hicimos una sola query, tomamos el indice [0] de cada campo.
    documentos = resultado["documents"][0]
    metadatas = resultado["metadatas"][0]
    distancias = resultado["distances"][0]

    # Armamos una lista de dicts mas comoda de usar en rag.py.
    # La función zip() va agrupando elementos de varias listas por posición.
    chunks = []
    for texto, meta, distancia in zip(documentos, metadatas, distancias):
        chunks.append({
            "texto": texto,
            "fuente": meta.get("fuente", "desconocida"),
            "distancia": distancia,
        })

    return chunks


def contar():
    '''
    Devuelve cuantos chunks hay guardados en la coleccion.
    Util para debug: despues de la ingesta, verificar que se cargaron.
    '''
    return _coleccion.count()


def vaciar():
    '''
    Borra TODA la coleccion y la vuelve a crear vacia.

    Util si queres re-cargar los documentos desde cero (evita chunks viejos de
    documentos que ya borraste). Lo llama cargar_documentos.py con la opcion --reset.
    '''
    global _coleccion
    _cliente.delete_collection(name=config.CHROMA_COLLECTION)
    _coleccion = _cliente.get_or_create_collection(
        name=config.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
