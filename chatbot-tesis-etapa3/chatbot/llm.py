# Modulo del LLM: genera la respuesta final en lenguaje natural.
'''
QUE HACE ESTE ARCHIVO:
Recibe la pregunta del usuario + el contexto (los chunks recuperados de la vector DB)
y le pide a GPT-4o-mini que redacte una respuesta natural basandose SOLO en ese contexto.

La pieza clave aca es el SYSTEM PROMPT: las instrucciones fijas que le damos al modelo
ANTES de cada conversacion. Le dicen quien es, que puede hacer, que NO puede hacer y como
responder. Es lo que evita que el bot invente ("alucine").

Igual que los otros modulos, este tiene una sola responsabilidad y no sabe de Chroma ni
del webhook: "dame pregunta + contexto, te devuelvo texto".
'''


# Importacion de modulos
'''
openai: el SDK. Usamos el mismo cliente que para embeddings, pero el metodo chat.completions.
config: para leer la API key y el nombre del modelo LLM.
'''
from openai import OpenAI
import config


# Cliente OpenAI, creado una vez al importar.
cliente = OpenAI(api_key=config.OPENAI_API_KEY)


# === SYSTEM PROMPT ===
'''
Este es el "instructivo" del bot. Esta escrito con reglas explicitas para:
1) Forzar que responda SOLO con el contexto provisto (anti-alucinacion).
2) Que admita cuando no sabe, en vez de inventar.
3) Definir el tono (cordial, breve, español argentino).

Es un string que vas a poder ajustar libremente para tu facultad: cambiar el nombre,
agregar reglas, etc. Es una de las partes que mas vas a iterar en la tesis.
'''
SYSTEM_PROMPT = '''Sos el asistente virtual de la facultad. Tu trabajo es responder preguntas \
de estudiantes basandote UNICAMENTE en la informacion de contexto que se te proporciona.

Reglas estrictas:
- Responde SOLO con informacion presente en el contexto. NUNCA inventes datos.
- Si la respuesta no esta en el contexto, decilo claramente: "No tengo esa informacion por \
ahora. Te sugiero consultar en la facultad." No intentes adivinar.
- Responde en español argentino, de forma cordial, clara y breve (2-4 oraciones cuando se pueda).
- Si el usuario pide un listado, devolvelo completo en viñetas aunque sea largo
- No menciones que estas usando "un contexto" ni hables de documentos; respondé de forma natural.
- Si la pregunta no tiene nada que ver con la facultad, redirigi amablemente al tema academico.
- Si el mensaje es un SALUDO (hola, buenas, buen dia, que onda, o cualquier
forma coloquial argentina): presentate en UNA sola oracion y ofrecele ayuda. 
En este casos NO apliques la regla de "no tengo esa informacion" y si usan expresiones coloquiales argentinas hacelo tambien.
- Si el mensaje es un AGRADECIMIENTO (gracias, genial, joya, de diez): respondé breve y cordial en UNA sola oracion. 
NO te presentes y NO enumeres lo que sabes hacer. En este casos NO apliques la regla de "no tengo esa informacion" 
y si usan expresiones coloquiales argentinas hacelo tambien.
- Si el mensaje es una DESPEDIDA (chau, nos vemos, hasta luego): despedite brevemente. NO te presentes. 
En este casos NO apliques la regla de "no tengo esa informacion" y si usan expresiones coloquiales argentinas hacelo tambien.

'''


def generar_respuesta(pregunta, contexto):
    '''
    Genera la respuesta del bot usando GPT-4o-mini.

    Parametros:
        pregunta: el texto que escribio el usuario.
        contexto: string con los chunks relevantes concatenados (lo arma rag.py).
                  Si esta vacio, igual llamamos al LLM, pero el system prompt hara que
                  responda "no tengo esa informacion".

    Devuelve:
        string con la respuesta redactada por el modelo.
    '''
    # Armamos el "mensaje de usuario" combinando el contexto y la pregunta.
    # El modelo de chat recibe una lista de mensajes con roles:
    #   - "system": las instrucciones fijas (quien es y como se comporta).
    #   - "user": lo que "dice" el usuario (aca metemos contexto + pregunta).
    mensaje_usuario = (
        f"Contexto disponible:\n{contexto}\n\n"
        f"Pregunta del estudiante: {pregunta}"
    )

    # Llamada a la API de chat.
    respuesta = cliente.chat.completions.create(
        model=config.OPENAI_LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mensaje_usuario},
        ],
        # temperature controla la "creatividad": 0 = mas determinista y fiel al contexto,
        # 1 = mas creativo (y mas riesgo de inventar). Para FAQ queremos algo bajo.
        temperature=0.2,
        # max_tokens limita el largo de la respuesta (control de costo y de verborragia).
        max_tokens=800,
    )

    # Extraemos el texto de la respuesta. choices[0] es la primera (y unica) respuesta.
    # .message.content es el texto generado. .strip() quita espacios sobrantes.
    return respuesta.choices[0].message.content.strip()
