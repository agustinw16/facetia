# Modulo encargado de ENVIAR mensajes a WhatsApp a traves de la Graph API de Meta.
'''
Este archivo concentra TODA la comunicacion saliente hacia Meta.
Si en el futuro queremos migrar a Twilio u otro proveedor, solo cambiamos este archivo
(y el parsing en webhook.py) sin tocar el resto del sistema.

Las funciones aca:
- armar_body_texto(): construye el JSON que Meta espera en su API.
- enviar_a_meta(): hace el POST HTTP a la Graph API.
'''


# Importacion de modulos
'''
requests: libreria para hacer peticiones HTTP a APIs externas (consume APIs de internet).
          La usamos para hacer POST a la Graph API de Meta.
json: libreria estandar de Python. La usamos para convertir un diccionario Python
      a un string JSON antes de mandarlo en el body del POST.
config: nuestro propio modulo que lee variables de entorno (.env).
        Desde aca accedemos a META_ACCESS_TOKEN y META_API_URL.
.utils: el archivo utils.py que esta en esta misma carpeta (whatsapp/).
        Importamos formatear_numero() para usarla al armar el body.
'''
import requests
import json
import config
from .utils import formatear_numero


def armar_body_texto(texto, numero):
    '''
    Construye el diccionario (que luego se serializa a JSON) que la Graph API
    de Meta espera para enviar un mensaje de tipo "texto" a un usuario.

    Esta funcion REEMPLAZA a enviarMensaje() de tu app.py original.
    El cambio principal es que ahora no agrega el prefijo "Esta es la respuesta a la pregunta:";
    simplemente envia el texto que le pasen. En esta Etapa 1 ese texto seguira siendo el eco;
    en la Etapa 3 sera la respuesta generada por la IA.

    Parametros:
        texto: el contenido del mensaje a enviar (string).
        numero: el numero del destinatario, recibido de Meta (string).

    Devuelve:
        Un diccionario con la estructura exacta que la Graph API requiere.
    '''
    # Formateamos el numero ANTES de armar el body (quita el "9" extra de celulares argentinos)
    numero_formateado = formatear_numero(numero)

    # Construimos el diccionario con la estructura que documenta Meta:
    # https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
    body = {
        "messaging_product": "whatsapp",   # siempre "whatsapp" cuando usamos WhatsApp Cloud API
        "recipient_type": "individual",     # mensaje a una persona (no a un grupo)
        "to": numero_formateado,            # numero del destinatario, ya formateado
        "type": "text",                     # tipo de mensaje: texto plano
        "text": {                           # contenido del mensaje
            "body": texto                   # el texto que le llega al usuario
        }
    }

    return body


def enviar_a_meta(body):
    '''
    Hace el POST a la Graph API de Meta para enviar el mensaje.

    Esta funcion REEMPLAZA a whatsappService() de tu app.py original.
    Mejoras respecto al original:
    - El token ahora se llama META_ACCESS_TOKEN (antes "VERIFY_TOKEN", que era confuso).
    - La URL y el token vienen de config.py (centralizado).
    - El error se imprime con mas detalle.

    Parametros:
        body: el diccionario con el mensaje, normalmente armado por armar_body_texto().

    Devuelve:
        True si Meta acepto el mensaje (status 200), False en cualquier otro caso.
    '''
    try:
        # Headers HTTP que la Graph API requiere.
        # Content-Type indica que estamos mandando JSON en el body.
        # Authorization lleva el Bearer token que prueba que somos nosotros.
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.META_ACCESS_TOKEN}"
        }

        # POST a la URL configurada en .env (la URL de Meta para mandar mensajes).
        # json.dumps() convierte el diccionario Python a string JSON.
        response = requests.post(
            config.META_API_URL,
            data=json.dumps(body),
            headers=headers
        )

        # Status 200 = mensaje aceptado por Meta (todavia no llego al usuario, pero esta encolado).
        if response.status_code == 200:
            return True
        else:
            # Si fallo, imprimimos el cuerpo de la respuesta para diagnosticar (token vencido, etc.).
            # En la Etapa 4 esto se reemplaza por logger.error().
            print(f"Error al enviar a Meta. Status: {response.status_code}. Body: {response.text}")
            return False

    # Captura cualquier error (sin internet, DNS roto, configuracion mal, etc.)
    except Exception as e:
        print(f"Excepcion al enviar a Meta: {e}")
        return False
