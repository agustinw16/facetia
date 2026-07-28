# Modulo encargado de RECIBIR mensajes (handshake + procesamiento), agnostico al proveedor.
'''
Cambios en ETAPA 3 respecto a etapa 2:

- RESPUESTA RAG: en vez de hacer eco, llamamos a chatbot.rag.responder() para generar
  una respuesta real basada en los documentos cargados.

- PROCESAMIENTO EN SEGUNDO PLANO (thread): el RAG tarda varios segundos (embeber +
  buscar + llamar al LLM). Meta/Twilio tienen un timeout de ~10-20s y si no contestamos
  rapido, REINTENTAN el mensaje (y el usuario recibiria respuestas duplicadas).
  Solucion: respondemos 200 INMEDIATAMENTE y hacemos el trabajo pesado en un thread aparte.

Mantiene de etapa 2:
- DEDUPLICACION por message_id.
- PERSISTENCIA de mensajes entrantes y salientes.
- PARSEO DEFENSIVO (el provider devuelve None si no es texto).

Sigue siendo GENERICO: no sabe si habla con Meta o Twilio.

NOTA IMPORTANTE sobre threads y Flask:
El objeto "request" de Flask SOLO existe durante el request HTTP. Un thread que arranca
despues NO puede acceder a "request". Por eso PARSEAMOS el mensaje en el hilo principal
(donde request si existe) y al thread le pasamos solo los datos ya extraidos (numero,
texto, message_id), que son simples strings.
'''


# Importacion de modulos
'''
threading: libreria estandar para correr codigo en un hilo separado (background).
flask.request: el HTTP entrante (solo accesible en el hilo principal del request).
.providers: factory obtener_provider().
database.connection / repositorio: persistencia.
chatbot.rag: el orquestador de la IA (la novedad de etapa 3).
'''
import threading
from flask import request
from .providers import obtener_provider
from database.connection import obtener_sesion
from database import repositorio
from chatbot import rag


def verificar_webhook():
    '''
    Maneja el GET inicial (handshake). Igual que en etapa 2: delega al provider.
    '''
    provider = obtener_provider()
    return provider.verificar_webhook(request)


def procesar_mensaje_entrante():
    '''
    Maneja el POST entrante. Su trabajo aca es MINIMO y RAPIDO:
    1) Parsear el mensaje (usa request, por eso va en el hilo principal).
    2) Si no es texto, responder 200 sin mas.
    3) Disparar el procesamiento pesado en un THREAD aparte.
    4) Responder 200 INMEDIATAMENTE (sin esperar al RAG).

    Asi Meta/Twilio reciben el 200 en milisegundos y no reintentan.
    '''
    provider = obtener_provider()

    # === 1) Parsear request (necesita "request", por eso aca y no en el thread) ===
    mensaje = provider.parsear_mensaje_entrante(request)

    # === 2) Si no es mensaje de texto, no procesamos ===
    if mensaje is None:
        return "EVENT_RECEIVED"

    numero = mensaje["numero"]
    texto = mensaje["texto"]
    message_id = mensaje["message_id"]

    print(f"[WEBHOOK] Entrante -> Numero: {numero} | Texto: {texto} | MessageID: {message_id}")

    # === 3) Disparar el trabajo pesado en segundo plano ===
    # target = la funcion a correr; args = los datos que le pasamos (strings simples).
    # daemon=True: el thread no impide que el proceso termine si hace falta.
    hilo = threading.Thread(
        target=_procesar_en_background,
        args=(numero, texto, message_id),
        daemon=True,
    )
    hilo.start()

    # === 4) Respuesta inmediata al proveedor (no espera al RAG) ===
    return "EVENT_RECEIVED"


def _procesar_en_background(numero, texto, message_id):
    '''
    Hace el trabajo pesado, FUERA del request HTTP. Aca SI podemos tardar varios segundos.

    Flujo:
    a) Abrir sesion de BD.
    b) DEDUPLICACION: si el message_id ya esta, no hacemos nada.
    c) Persistir usuario + mensaje entrante.
    d) Generar respuesta con RAG (embeber -> buscar -> LLM).
    e) Enviar la respuesta via provider.
    f) Persistir el mensaje saliente.
    g) Commit.

    El "_" inicial del nombre indica que es una funcion interna (no se usa desde afuera).
    '''
    # Obtenemos el provider (esta cacheado, es seguro usarlo desde el thread).
    provider = obtener_provider()

    try:
        with obtener_sesion() as sesion:

            # b) Deduplicacion: si ya procesamos este mensaje, cortamos.
            if repositorio.ya_fue_procesado(sesion, message_id):
                print(f"[WEBHOOK-BG] Mensaje duplicado ignorado: {message_id}")
                return

            # c) Usuario + mensaje entrante.
            usuario = repositorio.obtener_o_crear_usuario(sesion, numero)
            repositorio.guardar_mensaje_entrante(
                sesion=sesion,
                usuario_id=usuario.id,
                message_id_meta=message_id,
                texto=texto,
            )

            # d) === LA NOVEDAD DE ETAPA 3: generar respuesta con RAG ===
            # Antes era: respuesta = f"Esta es la respuesta a la pregunta: {texto}"
            # Ahora el bot responde con informacion real de los documentos.
            try:
                respuesta = rag.responder(texto)
            except Exception as e:
                # Si el RAG falla (OpenAI caido, sin saldo, etc), no dejamos al usuario
                # en silencio: le mandamos un mensaje generico y lo logueamos.
                print(f"[WEBHOOK-BG] Error en RAG: {e}")
                respuesta = ("Estoy teniendo problemas para responder en este momento. "
                             "Por favor, intenta de nuevo en unos minutos.")

            # e) Enviar la respuesta.
            envio_ok = provider.enviar_mensaje(numero, respuesta)

            # f) Persistir el mensaje saliente con su estado.
            estado = "enviado" if envio_ok else "fallido"
            repositorio.guardar_mensaje_saliente(
                sesion=sesion,
                usuario_id=usuario.id,
                texto=respuesta,
                estado=estado,
            )

            # g) Confirmar toda la transaccion.
            sesion.commit()

            if envio_ok:
                print("[WEBHOOK-BG] Respuesta enviada correctamente.")
            else:
                print("[WEBHOOK-BG] Fallo el envio de la respuesta.")

    except Exception as e:
        # Cualquier error inesperado en el background lo logueamos.
        # Como ya respondimos 200, no hay nada que devolverle al proveedor.
        print(f"[WEBHOOK-BG] Excepcion inesperada: {e}")
