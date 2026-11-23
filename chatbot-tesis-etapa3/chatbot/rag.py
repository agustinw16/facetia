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
Importamos los modulos hermanos del paquete chatbot (embeddings, vector_db, llm, avisos
y feriados). El "." indica "desde el mismo paquete (chatbot/)".
'''
from . import embeddings
from . import vector_db
from . import llm
from . import avisos
from . import feriados


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


def responder(pregunta, historial=None,perfil=None):
    '''
    Funcion principal del RAG. Recibe la pregunta del usuario y devuelve la respuesta.

    Es la UNICA funcion que el webhook necesita llamar.

    Tambien suma los avisos vigentes de la facultad (ver avisos.py) y los feriados
    nacionales proximos (ver feriados.py).

    Parametros:
        pregunta: el texto que escribio el usuario.
        historial: lista de dicts {"rol", "texto"} con los mensajes previos.
                   Opcional: si no se pasa, el bot responde sin memoria.
        perfil: (PERFIL) instrucciones de trato para este usuario, o None.
                El RAG no lo usa: solo se lo pasa al LLM.
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
    # le pasamos tambien el historial de la conversacion.
    # === [3b] AVISOS: traer los avisos vigentes de la planilla ===
    # Valen para TODOS los usuarios, por eso los busca el RAG y no el webhook.
    # Ojo con el nombre: "avisos" ya es el modulo importado arriba; si la variable
    # tambien se llamara "avisos", taparia al modulo. Por eso se llama texto_avisos.
    texto_avisos = avisos.obtener_avisos_vigentes()

    # === [3c] FERIADOS: traer los feriados nacionales proximos ===
    # Mismo motivo que los avisos: valen para todos, por eso los busca el RAG.
    # estado_hoy_manana_texto() va SIEMPRE primero: es el dato mas pedido
    # ("hoy"/"mañana" hay clases?) y lo calculamos en Python para que el LLM no
    # tenga que deducirlo el (ver el docstring de esa funcion en feriados.py).
    texto_feriados = feriados.estado_hoy_manana_texto()
    texto_proximos = feriados.feriados_proximos_texto()
    if texto_proximos:
        texto_feriados = f"{texto_feriados}\n\n{texto_proximos}"

    respuesta = llm.generar_respuesta(
        pregunta, contexto, historial, perfil, avisos=texto_avisos, feriados=texto_feriados
    )
    print(f"[RAG] Respuesta generada ({len(respuesta)} caracteres).")

    return respuesta
