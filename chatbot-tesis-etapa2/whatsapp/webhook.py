# Modulo encargado de RECIBIR mensajes (handshake + procesamiento), agnostico al proveedor.
'''
Cambios en ETAPA 2 respecto a etapa 1:

- DEDUPLICACION: antes de procesar, consultamos la BD para ver si ya recibimos
  este message_id. Si si, devolvemos 200 sin procesar (Meta/Twilio puede reintentar
  el mismo mensaje varias veces).

- PARSEO DEFENSIVO: el provider ya devuelve None si el JSON entrante no es un
  mensaje de texto (audio, status, sticker, etc). Aca lo manejamos sin tirar
  excepciones.

- PERSISTENCIA: cada mensaje (entrante y saliente) queda guardado en la BD.
  Util para metricas, debug y dedup futuro.

Sigue siendo GENERICO: no sabe si esta hablando con Meta o con Twilio.
Solo le pide al provider que parsee y envie.
'''


# Importacion de modulos
'''
flask: importamos request para acceder al HTTP entrante.
.providers: nuestro factory obtener_provider() que devuelve el provider segun el .env.
database.connection: para obtener una sesion de BD por cada request.
database.repositorio: funciones de alto nivel para CRUD (obtener_o_crear_usuario, etc.).
'''
from flask import request
from .providers import obtener_provider
from database.connection import obtener_sesion
from database import repositorio


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

    Flujo (etapa 2):
    1) Provider parsea el request en formato normalizado.
    2) Si no es mensaje de texto (audio/status/etc), devolvemos 200 sin procesar.
    3) DEDUPLICACION: si el message_id ya esta en la BD, devolvemos 200 sin reprocesar.
    4) Persistimos al usuario (crear o actualizar ultimo_visto).
    5) Persistimos el mensaje entrante.
    6) Armamos la respuesta (en etapa 2 es eco; en etapa 3 sera RAG).
    7) Provider envia la respuesta al usuario.
    8) Persistimos el mensaje saliente.
    9) Devolvemos 200 para que el proveedor no reintente.
    '''
    try:
        provider = obtener_provider()

        # === 1) Parsear request usando provider activo ===
        mensaje = provider.parsear_mensaje_entrante(request)

        # === 2) Si no es mensaje de texto, no procesamos ===
        if mensaje is None:
            return "EVENT_RECEIVED"

        numero = mensaje["numero"]
        texto = mensaje["texto"]
        message_id = mensaje["message_id"]

        print(f"[WEBHOOK] Numero: {numero} | Texto: {texto} | MessageID: {message_id}")

        # Abrimos sesion de BD para hacer dedup + persistencia.
        # "with" garantiza que se cierre al salir, incluso si hay excepcion.
        with obtener_sesion() as sesion:

            # === 3) Deduplicacion ===
            if repositorio.ya_fue_procesado(sesion, message_id):
                print(f"[WEBHOOK] Mensaje duplicado ignorado: {message_id}")
                return "EVENT_RECEIVED"

            # === 4) Buscar o crear usuario ===
            usuario = repositorio.obtener_o_crear_usuario(sesion, numero)

            # === 5) Guardar mensaje entrante ===
            repositorio.guardar_mensaje_entrante(
                sesion=sesion,
                usuario_id=usuario.id,
                message_id_meta=message_id,
                texto=texto,
            )

            # === 6) Armar respuesta (eco en esta etapa) ===
            # En etapa 3 esta linea se reemplaza por: respuesta = rag.responder(texto)
            respuesta = f"Esta es la respuesta a la pregunta: {texto}"

            # === 7) Enviar respuesta via provider ===
            envio_ok = provider.enviar_mensaje(numero, respuesta)

            # === 8) Guardar mensaje saliente ===
            # Si fallo el envio, lo marcamos como "fallido" en la BD para tenerlo
            # como evidencia (en etapa 4 podriamos reintentar).
            estado = "enviado" if envio_ok else "fallido"
            repositorio.guardar_mensaje_saliente(
                sesion=sesion,
                usuario_id=usuario.id,
                texto=respuesta,
                estado=estado,
            )

            # Commit explicito: confirmamos toda la transaccion (usuario + 2 mensajes).
            # Si algo falla antes de aca, no se guarda NADA (atomicidad).
            sesion.commit()

            if envio_ok:
                print("[WEBHOOK] Respuesta enviada correctamente.")
            else:
                print("[WEBHOOK] Fallo el envio de la respuesta.")

        # === 9) Respuesta OBLIGATORIA a Meta/Twilio ===
        return "EVENT_RECEIVED"

    except Exception as e:
        # Cualquier excepcion no controlada: la logueamos pero devolvemos 200 igual
        # para que el proveedor no entre en loop de reintentos.
        # En etapa 4 mejoraremos esto con logger estructurado.
        print(f"[WEBHOOK] Excepcion inesperada: {e}")
        return "EVENT_RECEIVED"
