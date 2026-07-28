# Modulo RAG: el ORQUESTADOR que une embeddings + vector DB + LLM.
'''
Este es el "director de orquesta" de la etapa 3. No hace el trabajo pesado el mismo;
coordina a los otros tres modulos en el orden correcto:

    pregunta del usuario
          |
    [1] embeddings.embeber_texto()   -> convierte la pregunta en vector
          |
    [2] vector_db.buscar_similares() -> trae los chunks mas parecidos
          |
    [3] (armar el contexto con esos chunks)
          |
    [4] llm.generar_respuesta()      -> redacta la respuesta final
          |
    respuesta para el usuario

El webhook.py va a llamar a UNA sola funcion de aca: responder(pregunta).
Asi el webhook no necesita saber nada de embeddings, Chroma ni OpenAI.

Esta es la "R", la "A" y la "G" de RAG:
- Retrieval (recuperacion): pasos 1 y 2.
- Augmented (aumentada): paso 3 (le sumamos el contexto a la pregunta).
- Generation (generacion): paso 4.
'''


# Importacion de modulos
'''
Importamos los tres modulos hermanos del paquete chatbot.
El "." indica "desde el mismo paquete (chatbot/)".
'''
from . import embeddings
from . import vector_db
from . import llm


def _armar_contexto(chunks):
    '''
    Convierte la lista de chunks (dicts) en un solo string de texto para pasarle al LLM.

    Numeramos cada fragmento y mencionamos su fuente. Esto ayuda al modelo a organizar
    la informacion y, si quisieras, a citar de donde salio.

    Parametros:
        chunks: lista de dicts {"texto", "fuente", "distancia"} que devolvio vector_db.

    Devuelve:
        string con todos los fragmentos concatenados.
    '''
    if not chunks:
        return ""

    '''
     - "partes = []": Crea una lista vacía.
     - "for i, chunk in enumerate(chunks, start=1)": Recorre todos los elementos de chunks. La función enumerate() agrega un contador.
     - "partes.append": Agrega un texto a la lista partes. f Permite insertar variables dentro del texto
    '''
    partes = [] 
    for i, chunk in enumerate(chunks, start=1):
        partes.append(f"[Fragmento {i} - fuente: {chunk['fuente']}]\n{chunk['texto']}")

    # Separamos los fragmentos con doble salto de linea para que queden bien delimitados.
    return "\n\n".join(partes)


def responder(pregunta):
    '''
    Funcion principal del RAG. Recibe la pregunta del usuario y devuelve la respuesta.

    Es la UNICA funcion que el webhook necesita llamar.

    Parametros:
        pregunta: el texto que escribio el usuario.

    Devuelve:
        string con la respuesta lista para enviar por WhatsApp.
    '''
    # === [1] Embeber la pregunta ===
    # Convertimos la pregunta en un vector para poder compararla con los chunks.
    print(f"[RAG] Embebiendo pregunta: {pregunta!r}")
    vector_pregunta = embeddings.embeber_texto(pregunta)

    # === [2] Buscar chunks similares ===
    # Traemos los top-K fragmentos mas parecidos en significado.
    chunks = vector_db.buscar_similares(vector_pregunta)
    print(f"[RAG] Se recuperaron {len(chunks)} chunks de la base de conocimiento.")

    # === [3] Armar el contexto ===
    # Concatenamos los chunks en un solo texto para el LLM.
    contexto = _armar_contexto(chunks)

    # === [4] Generar la respuesta ===
    # El LLM redacta la respuesta usando SOLO el contexto (gracias al system prompt).
    # Si el contexto esta vacio (no se cargaron documentos o ninguno era relevante),
    # el system prompt hace que el modelo responda "no tengo esa informacion".
    respuesta = llm.generar_respuesta(pregunta, contexto)
    print(f"[RAG] Respuesta generada ({len(respuesta)} caracteres).")

    return respuesta
