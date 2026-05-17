# Implementacion del provider para Twilio (WhatsApp via Twilio Cloud).
'''
Este archivo concentra TODA la logica especifica de Twilio.

Diferencias clave con Meta:
1) Twilio NO hace handshake GET. Cuando configuras el webhook en el panel de Twilio,
   queda activo de inmediato. Para mantener la interfaz uniforme, verificar_webhook()
   simplemente devuelve "OK" para responder a un GET si alguien lo hace.

2) Twilio envia los mensajes entrantes como x-www-form-urlencoded (formulario HTTP), NO como JSON.
   Por eso usamos request.form en vez de request.get_json().

3) Twilio usa un SDK oficial de Python (libreria "twilio") que abstrae el llamado HTTP.
   No hacemos requests.post() a mano, le pedimos al Client que envie el mensaje.

4) Twilio requiere prefijar el numero con "whatsapp:" (ej: "whatsapp:+5491112345678").

Por que mantener la misma interfaz: el resto del codigo (webhook.py) NO sabe ni le importa
si esta hablando con Meta o con Twilio. Solo llama a provider.parsear_mensaje_entrante() y
provider.enviar_mensaje().
'''


# Importacion de modulos
'''
twilio.rest.Client: cliente principal del SDK de Twilio. Lo usamos para enviar mensajes.
config: variables de entorno (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM).
..utils: subimos un nivel para llegar a utils.py (formatear_numero).
.base: WhatsAppProvider, la clase abstracta de la que heredamos.
'''
from twilio.rest import Client
import config
from ..utils import formatear_numero
from .base import WhatsAppProvider


class TwilioProvider(WhatsAppProvider):
    '''
    Implementacion concreta del provider para Twilio.

    En el constructor inicializamos el Client de Twilio una sola vez
    (reutilizable para todos los envios).
    '''

    def __init__(self):
        '''
        Constructor: inicializa el cliente de Twilio con las credenciales del .env.
        Se llama UNA SOLA VEZ cuando el factory crea la instancia.
        '''
        self.client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

    def verificar_webhook(self, request):
        '''
        Twilio NO hace handshake GET como Meta.

        Cuando configuras la URL del webhook en el panel de Twilio (Console -> Messaging
        -> Settings -> WhatsApp sandbox settings), Twilio simplemente guarda la URL y empieza
        a hacer POST cuando llegan mensajes. No hay verificacion previa.

        Este metodo existe solo para cumplir con la interfaz abstracta. Si alguien hace
        GET a la URL, devolvemos "OK" en vez de un 404.
        '''
        print("[TWILIO] GET recibido al webhook. Twilio no requiere handshake; devolviendo OK.")
        return "OK"

    def parsear_mensaje_entrante(self, request):
        '''
        Parsea el formulario HTTP que Twilio envia cuando llega un mensaje.

        Twilio envia los datos como application/x-www-form-urlencoded (NO JSON).
        Por eso usamos request.form, no request.get_json().

        Campos relevantes:
        - From: "whatsapp:+5491112345678" (incluye prefijo "whatsapp:" y "+")
        - Body: "Hola que tal"
        - MessageSid: "SMxxxxxxxxxxxxx" (ID unico del mensaje, sirve para deduplicar)
        - NumMedia: "0" si es texto, ">0" si es audio/imagen/etc.

        Devuelve dict normalizado o None si no es un mensaje de texto.
        '''
        try:
            print(f"[TWILIO] Mensaje recibido: {dict(request.form)}")

            # Si NumMedia > 0, es un mensaje con multimedia (audio, imagen, etc).
            # En esta etapa solo procesamos texto.
            num_media = int(request.form.get("NumMedia", "0"))
            if num_media > 0:
                print("[TWILIO] Mensaje con multimedia. Ignorando en esta etapa.")
                return None

            # Extraer campos. .get() devuelve None si la clave no existe (no rompe).
            from_field = request.form.get("From", "")
            body = request.form.get("Body", "")
            message_sid = request.form.get("MessageSid", "")

            # Si falta alguno de los campos criticos, no podemos procesar
            if not from_field or not body or not message_sid:
                print("[TWILIO] Faltan campos requeridos en el POST.")
                return None

            # Limpiar el numero: Twilio lo envia como "whatsapp:+5491112345678".
            # Queremos solo "5491112345678" (sin prefijo, sin "+") para mantener el formato igual al de Meta.
            numero = from_field.replace("whatsapp:", "").replace("+", "")

            return {
                "numero": numero,
                "texto": body,
                "message_id": message_sid,
            }

        except Exception as e:
            print(f"[TWILIO] Excepcion al parsear: {e}")
            return None

    def enviar_mensaje(self, numero, texto):
        '''
        Envia un mensaje de texto al usuario via SDK de Twilio.

        El SDK abstrae el POST HTTP. Internamente hace algo parecido a Meta, pero
        nos da una API mas linda.

        Importante: Twilio requiere prefijar el numero con "whatsapp:+", tanto el "from"
        como el "to". El TWILIO_WHATSAPP_FROM ya viene con el prefijo desde el .env
        (ej: "whatsapp:+14155238886" del sandbox).
        '''
        try:
            # Formatear el numero (quita el "9" extra de celulares argentinos)
            numero_formateado = formatear_numero(numero)

            # Llamada al SDK de Twilio. Internamente hace un POST a la API de Twilio.
            message = self.client.messages.create(
                from_=config.TWILIO_WHATSAPP_FROM,  # ej: "whatsapp:+14155238886"
                body=texto,
                to=f"whatsapp:+{numero_formateado}",
            )

            # message.sid es el ID que Twilio asigna al mensaje saliente.
            # Si llego aca sin excepcion, fue enviado correctamente.
            print(f"[TWILIO] Mensaje enviado correctamente. SID: {message.sid}")
            return True

        except Exception as e:
            print(f"[TWILIO] Excepcion al enviar mensaje: {e}")
            return False
