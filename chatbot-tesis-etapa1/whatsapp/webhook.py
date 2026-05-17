# Modulo encargado de RECIBIR mensajes desde WhatsApp (webhook entrante).
'''
Aca vive toda la logica que procesa lo que Meta nos envia.

Hay dos cosas que Meta nos manda al webhook:

1) HANDSHAKE (GET): cuando configuras el webhook por primera vez en Meta,
   ellos hacen un GET con un challenge para verificar que la URL es tuya.
   La funcion verificar_webhook() responde a esto.

2) MENSAJES (POST): cuando un usuario te escribe por WhatsApp, Meta hace POST
   con un JSON que describe el mensaje. La funcion procesar_mensaje_entrante() lo parsea
   y dispara la respuesta.

Esta version es de Etapa 1: por ahora hacemos eco (devolvemos el mismo texto recibido).
En Etapa 3 cambiaremos esta logica para que llame al RAG y devuelva una respuesta inteligente.
'''


# Importacion de modulos
'''
flask: importamos "request" para acceder al request HTTP entrante (query params, body, etc.).
config: nuestras variables de entorno (token de verificacion).
.sender: funciones de envio que estan en whatsapp/sender.py (misma carpeta).
'''
from flask import request
import config
from .sender import armar_body_texto, enviar_a_meta


def verificar_webhook():
    '''
    Responde al handshake GET de Meta cuando configuras el webhook por primera vez.

    Flujo:
    1) Meta hace GET /whatsapp?hub.verify_token=XXX&hub.challenge=YYY
    2) Si XXX coincide con nuestro META_VERIFY_TOKEN, devolvemos YYY.
    3) Si no coincide, devolvemos error 400.

    Esta funcion REEMPLAZA a VerifyToken() de tu app.py original.
    Diferencia clave: el token ya NO esta hardcodeado, viene del .env via config.
    '''
    try:
        # Extraemos los parametros que Meta envia en la URL (query string).
        # request.args.get(nombre) devuelve el valor o None si no existe.
        token_recibido = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        # Comparamos el token que mando Meta contra el nuestro (definido en .env).
        if token_recibido == config.META_VERIFY_TOKEN:
            print("Webhook verificado correctamente con Meta.")
            # IMPORTANTE: hay que devolver el challenge en TEXTO PLANO, no como JSON.
            return challenge
        else:
            # Token incorrecto: alguien intento configurar nuestro webhook sin saber el secreto.
            print(f"Intento de verificacion con token incorrecto: {token_recibido}")
            return "error", 400

    except Exception as e:
        # Cualquier error inesperado (parametros faltantes, etc.).
        print(f"Excepcion en verificar_webhook: {e}")
        return "error", 400


def procesar_mensaje_entrante():
    '''
    Procesa un mensaje POST que recibimos de Meta cuando un usuario nos escribe.

    Flujo:
    1) Meta hace POST /whatsapp con un JSON enorme describiendo el mensaje.
    2) Extraemos el numero del usuario y el texto que escribio.
    3) Armamos una respuesta (en esta Etapa 1 es eco; en Etapa 3 sera la IA).
    4) Enviamos la respuesta llamando a Graph API via enviar_a_meta().
    5) Devolvemos "EVENT_RECEIVED" para que Meta sepa que recibimos el evento.

    Esta funcion REEMPLAZA a ReceivedMessage() de tu app.py original.
    En Etapa 1 conservamos el comportamiento de eco para validar que la reestructuracion
    no rompio nada. Las mejoras de parsing y deduplicacion vienen en Etapa 2.
    '''
    try:
        # Convierte el body JSON del POST en un diccionario Python.
        received = request.get_json()
        print(f"Mensaje recibido de Meta: {received}")

        # Navegacion del JSON anidado que envia Meta.
        # Estructura: entry[0] -> changes[0] -> value -> messages[0] -> {from, text.body}
        # IMPORTANTE: esta navegacion es FRAGIL (rompe si llega un audio o un status).
        # En Etapa 2 la mejoraremos con parseo defensivo.
        entry = received["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value["messages"][0]

        # Datos relevantes que vamos a usar para responder
        numero = messages["from"]                    # numero del usuario que escribio
        texto_usuario = messages["text"]["body"]      # contenido del mensaje

        print(f"Numero: {numero} | Texto: {texto_usuario}")

        # === ETAPA 1: ECO ===
        # Devolvemos el mismo texto que mando el usuario, con un prefijo aclaratorio.
        # En Etapa 3 esta linea se reemplaza por algo como:
        #     respuesta = rag.responder(texto_usuario)
        respuesta = f"Esta es la respuesta a la pregunta: {texto_usuario}"

        # Armar el body JSON que Meta espera y enviarlo
        body = armar_body_texto(respuesta, numero)
        envio_ok = enviar_a_meta(body)

        if envio_ok:
            print("Respuesta enviada correctamente al usuario.")
        else:
            print("Fallo el envio de la respuesta al usuario.")

        # Respuesta OBLIGATORIA a Meta: confirma que recibimos el evento.
        # Si no devolvemos esto rapido, Meta reintenta el mensaje (causa duplicados).
        return "EVENT_RECEIVED"

    except Exception as e:
        # Excepcion comun en esta etapa: el JSON no era de un mensaje de texto
        # (puede ser un status de "entregado/leido", un audio, una imagen, etc.).
        # Devolvemos igual "EVENT_RECEIVED" porque Meta espera 200; si devolvemos error
        # entra en loop de reintentos.
        print(f"Excepcion procesando mensaje: {e}")
        return "EVENT_RECEIVED"
