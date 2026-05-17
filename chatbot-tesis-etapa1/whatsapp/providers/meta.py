# Implementacion del provider para Meta Cloud API (WhatsApp Business).
'''
Este archivo concentra TODA la logica especifica de Meta:
- Como hace el handshake (GET con hub.verify_token + hub.challenge).
- Como parsea el JSON anidado que Meta nos envia en cada mensaje.
- Como envia mensajes a la Graph API (POST con Authorization Bearer).

Si en el futuro Meta cambia su API, solo este archivo se actualiza.
El resto del codigo (webhook.py, app.py) NO se entera.

Reemplaza a:
- whatsapp/sender.py (que se elimina)
- La logica de Meta que estaba en whatsapp/webhook.py (que se vuelve generico)
'''


# Importacion de modulos
'''
requests: para hacer POST HTTP a la Graph API de Meta.
json: para serializar el body del POST.
config: nuestras variables de entorno (META_ACCESS_TOKEN, META_API_URL).
..utils: dos puntos porque subimos un nivel (providers/ -> whatsapp/) para llegar a utils.py.
.base: WhatsAppProvider, la clase abstracta de la que heredamos.
'''
import requests
import json
import config
from ..utils import formatear_numero
from .base import WhatsAppProvider


class MetaProvider(WhatsAppProvider):
    '''
    Implementacion concreta del provider para Meta Cloud API.

    Hereda de WhatsAppProvider y SOBRESCRIBE los 3 metodos abstractos
    con la logica especifica de Meta.
    '''

    def verificar_webhook(self, request):
        '''
        Maneja el handshake GET que Meta hace al configurar el webhook.

        Flujo:
        1) Meta hace GET /whatsapp?hub.verify_token=XXX&hub.challenge=YYY
        2) Si XXX coincide con nuestro META_VERIFY_TOKEN, devolvemos YYY.
        3) Si no coincide, devolvemos error 400.

        Este metodo REEMPLAZA a la funcion verificar_webhook() que estaba antes en webhook.py.
        '''
        try:
            # Extraemos los parametros que Meta envia en la URL (query string)
            token_recibido = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")

            # Comparamos el token contra el nuestro (definido en .env)
            if token_recibido == config.META_VERIFY_TOKEN:
                print("[META] Webhook verificado correctamente.")
                # IMPORTANTE: hay que devolver el challenge en TEXTO PLANO, no como JSON
                return challenge
            else:
                print(f"[META] Intento de verificacion con token incorrecto: {token_recibido}")
                return "error", 400

        except Exception as e:
            print(f"[META] Excepcion en verificar_webhook: {e}")
            return "error", 400

    def parsear_mensaje_entrante(self, request):
        '''
        Parsea el JSON anidado que Meta envia cuando llega un mensaje.

        Estructura del JSON de Meta:
        {
          "entry": [{
            "changes": [{
              "value": {
                "messages": [{
                  "from": "5491112345678",
                  "id": "wamid.XXXX",
                  "text": {"body": "Hola"}
                }]
              }
            }]
          }]
        }

        Devuelve un dict NORMALIZADO o None si no se puede procesar.
        '''
        try:
            received = request.get_json()
            print(f"[META] Mensaje recibido: {received}")

            # Navegacion defensiva del JSON anidado.
            # En etapa 1 lo dejamos simple (con try/except), en etapa 2 lo mejoramos.
            entry = received["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]

            # Si no hay "messages" en value, es un status update (entregado, leido), no un mensaje
            if "messages" not in value:
                print("[META] El payload no es un mensaje (probablemente un status). Ignorando.")
                return None

            messages = value["messages"][0]

            # Solo procesamos mensajes de tipo "text" en esta etapa.
            # Audios, imagenes, ubicaciones, stickers se ignoran (no rompen).
            if messages.get("type") != "text":
                print(f"[META] Tipo de mensaje no soportado: {messages.get('type')}. Ignorando.")
                return None

            return {
                "numero": messages["from"],
                "texto": messages["text"]["body"],
                "message_id": messages["id"],
            }

        except (KeyError, IndexError, TypeError) as e:
            # Si el JSON no tiene la estructura esperada, devolvemos None.
            # Meta tambien manda eventos de "status" que NO son mensajes; no son errores.
            print(f"[META] No se pudo parsear (probablemente no es un mensaje): {e}")
            return None
        except Exception as e:
            print(f"[META] Excepcion inesperada en parseo: {e}")
            return None

    def enviar_mensaje(self, numero, texto):
        '''
        Envia un mensaje de texto al usuario via Graph API.

        Reemplaza a las funciones armar_body_texto() y enviar_a_meta() que estaban en sender.py.
        Ahora estan unificadas en este metodo.
        '''
        try:
            # Formateamos el numero (quita el "9" extra de celulares argentinos)
            numero_formateado = formatear_numero(numero)

            # Body que la Graph API espera. Documentacion:
            # https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
            body = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": numero_formateado,
                "type": "text",
                "text": {"body": texto},
            }

            # Headers HTTP que Graph API requiere
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.META_ACCESS_TOKEN}",
            }

            # POST a la URL configurada en .env
            response = requests.post(
                config.META_API_URL,
                data=json.dumps(body),
                headers=headers,
            )

            if response.status_code == 200:
                print("[META] Mensaje enviado correctamente.")
                return True
            else:
                print(f"[META] Error al enviar. Status: {response.status_code}. Body: {response.text}")
                return False

        except Exception as e:
            print(f"[META] Excepcion al enviar mensaje: {e}")
            return False
