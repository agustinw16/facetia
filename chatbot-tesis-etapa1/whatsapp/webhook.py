# Modulo encargado de RECIBIR mensajes (handshake + procesamiento), agnostico al proveedor.
'''
Este archivo es GENERICO: no sabe si esta hablando con Meta o con Twilio.
Solo le pide al "provider" (obtenido del factory) que parsee el request entrante
y que envie la respuesta.

Toda la logica especifica de cada proveedor vive en whatsapp/providers/meta.py
o whatsapp/providers/twilio.py.

Si manana agregamos un tercer proveedor (ej: 360dialog), este archivo NO se toca.
Solo creamos providers/dialog360.py.

Esta es la magia del patron Strategy: el codigo cliente depende de una INTERFAZ ABSTRACTA,
no de implementaciones concretas. En la tesis se defiende como "Inversion de Dependencias".
'''


# Importacion de modulos
'''
flask: importamos request para acceder al HTTP entrante.
.providers: nuestro factory obtener_provider() que devuelve el provider segun el .env.
'''
from flask import request
from .providers import obtener_provider


def verificar_webhook():
    '''
    Maneja el GET inicial (handshake).

    Delegamos al provider:
    - Meta: valida el hub.verify_token y devuelve el challenge.
    - Twilio: no hace handshake, devuelve "OK".

    El codigo de aca no sabe ni le importa la diferencia.
    '''
    provider = obtener_provider()
    return provider.verificar_webhook(request)


def procesar_mensaje_entrante():
    '''
    Procesa un POST entrante con un mensaje del usuario.

    Flujo:
    1) Pedimos al provider que parsee el request en formato normalizado.
    2) Si es None (no era un mensaje de texto), devolvemos 200 y listo.
    3) Si es un mensaje, armamos la respuesta (en etapa 1 es eco; en etapa 3 sera RAG).
    4) Pedimos al provider que envie la respuesta al usuario.
    5) Devolvemos 200 para que Meta/Twilio no reintente.
    '''
    try:
        provider = obtener_provider()

        # Parseamos el request usando la logica especifica del provider activo
        mensaje = provider.parsear_mensaje_entrante(request)

        # Si no es un mensaje de texto procesable (audio, status, etc), respondemos 200 y listo
        if mensaje is None:
            return "EVENT_RECEIVED"

        print(f"[WEBHOOK] Numero: {mensaje['numero']} | Texto: {mensaje['texto']}")

        # === ETAPA 1: ECO ===
        # Devolvemos el mismo texto que mando el usuario.
        # En etapa 3 esta linea se reemplaza por: respuesta = rag.responder(mensaje['texto'])
        respuesta = f"Esta es la respuesta a la pregunta: {mensaje['texto']}"

        # Pedimos al provider que envie la respuesta. Provider sabe como hacerlo.
        envio_ok = provider.enviar_mensaje(mensaje["numero"], respuesta)

        if envio_ok:
            print("[WEBHOOK] Respuesta enviada correctamente.")
        else:
            print("[WEBHOOK] Fallo el envio de la respuesta.")

        # Respuesta OBLIGATORIA: confirma que recibimos el evento.
        # Si no devolvemos 200 rapido, el proveedor reintenta el mensaje (causa duplicados).
        return "EVENT_RECEIVED"

    except Exception as e:
        # Cualquier excepcion no controlada: la logueamos pero devolvemos 200 igual
        # para que el proveedor no entre en loop de reintentos.
        print(f"[WEBHOOK] Excepcion inesperada: {e}")
        return "EVENT_RECEIVED"
