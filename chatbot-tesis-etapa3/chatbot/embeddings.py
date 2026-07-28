# Modulo de EMBEDDINGS: convierte texto en vectores numericos.
'''
QUE ES UN EMBEDDING (repaso conceptual):
Un embedding es una lista de numeros (un "vector") que representa el SIGNIFICADO de un texto.
OpenAI con el modelo text-embedding-3-small devuelve un vector de 1536 numeros por cada texto.

La magia: textos con significado parecido producen vectores parecidos, AUNQUE usen
palabras distintas.
    "Cuando empiezan las clases?"      -> [0.12, -0.45, 0.78, ...]
    "Fecha de inicio del cuatrimestre" -> [0.13, -0.44, 0.77, ...]  (muy parecido)
    "Menu del comedor"                 -> [0.91,  0.22, -0.05, ...] (muy distinto)

Esto es lo que permite BUSCAR POR SIGNIFICADO en vez de por coincidencia exacta de palabras.

ESTE ARCHIVO tiene una sola responsabilidad: "dame texto(s), te devuelvo su(s) vector(es)".
No sabe nada de ChromaDB ni del LLM. Es una pieza chica y testeable.
'''


# Importacion de modulos
'''
openai: el SDK oficial. La clase OpenAI es el cliente que habla con la API.
config: para leer la API key y el nombre del modelo de embeddings.
'''
from openai import OpenAI
import config


# Creamos el cliente UNA sola vez al importar el modulo.
'''
El cliente OpenAI() lee la API key que le pasamos. Lo creamos a nivel de modulo
(no dentro de la funcion) para no reinstanciarlo en cada llamada: es mas eficiente.
'''
cliente = OpenAI(api_key=config.OPENAI_API_KEY)

'''
Tendremos 2 funciones: 
embeber_texto es para el flujo de consulta (1 pregunta a la vez, preguntas de alumnos) 
embeber_lote es para el flujo de carga (muchos documentos de una, los documentos de los que se alimenta la DB).
'''
def embeber_texto(texto):
    '''
    Convierte UN texto en su vector de embedding.

    Se usa principalmente para embeber la PREGUNTA del usuario en tiempo real
    (cuando llega un mensaje al webhook).

    Parametros:
        texto: string a convertir en vector.

    Devuelve:
        lista de floats (el vector de 1536 dimensiones).
    '''
    # Limpiamos saltos de linea: la API los acepta, pero reemplazarlos por espacios
    # da embeddings ligeramente mas estables segun la doc de OpenAI.
    texto = texto.replace("\n", " ")

    # Llamada a la API. input puede ser un texto o una lista de textos.
    '''
     - "cliente" Es el objeto que representa la conexión con OpenAI. Con este objeto se puede llamar a distintos servicios:
     - "cliente.embeddings.create" Es una función que envía una petición a la API de OpenAI para crear embeddings.
     - "model=config.OPENAI_EMBEDDING_MODEL" Indica qué modelo de embeddings usar.
     - "input=texto" Es el texto que querés convertir a embedding.
    '''
    respuesta = cliente.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=texto,
    )

    # La respuesta trae una lista "data"; como mandamos un solo texto, tomamos el [0].
    # .embedding es el vector en si (la lista de numeros).
    return respuesta.data[0].embedding


def embeber_lote(textos):
    '''
    Convierte una LISTA de textos en una lista de vectores, en UNA sola llamada.

    Se usa en la INGESTA (cargar_documentos.py): cuando tenemos muchos chunks,
    es mucho mas rapido y barato mandarlos todos juntos que uno por uno.

    Parametros:
        textos: lista de strings.

    Devuelve:
        lista de vectores (lista de listas de floats), en el MISMO orden que la entrada.
    '''
    # Misma limpieza de saltos de linea, aplicada a cada texto de la lista.
    textos_limpios = [t.replace("\n", " ") for t in textos]

    # Una sola llamada con toda la lista. OpenAI procesa el lote y devuelve un vector por texto.
    respuesta = cliente.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=textos_limpios,
    )

    # Importante: OpenAI puede devolver los resultados desordenados, pero cada item trae
    # su "index". Ordenamos por index para garantizar que el vector i corresponde al texto i.
    items_ordenados = sorted(respuesta.data, key=lambda item: item.index)
    return [item.embedding for item in items_ordenados]
