# Importacion de modulos
'''
os: libreria estandar de Python para acceder a variables de entorno.
dotenv: libreria externa que lee el archivo .env y carga sus valores en os.environ.
       Sin esto, las variables del .env solo existirian "en el archivo" pero no
       estarian accesibles desde el codigo.
'''
import os
from dotenv import load_dotenv

# Cargar variables del archivo .env al entorno del proceso
'''
load_dotenv() busca un archivo ".env" en el directorio actual (o en directorios padres)
y mete cada linea "CLAVE=valor" como una variable de entorno disponible via os.getenv().

En PRODUCCION (Render), las variables se configuran directamente en el panel y no hace falta .env;
load_dotenv() simplemente no hace nada si no encuentra el archivo, asi que es seguro dejarlo.
'''
load_dotenv()


# === META / WHATSAPP CLOUD API ===

# Token de verificacion del webhook (handshake GET)
'''
Cuando Meta hace GET /whatsapp con ?hub.verify_token=XXXX, comparamos XXXX contra
este valor. Si coinciden, devolvemos el challenge. Si no, devolvemos 400.
Antes estaba HARDCODEADO en el codigo ("myaccestokensecreto"); ahora viene del .env.
'''
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")

# Token Bearer para autenticar las llamadas a Graph API (envio de mensajes)
'''
Este es DISTINTO al META_VERIFY_TOKEN. Lo usa "whatsapp/sender.py" en el header
Authorization para que Meta acepte nuestros envios.
En el codigo viejo se llamaba "VERIFY_TOKEN" (nombre confuso); ahora le pusimos su nombre real.
'''
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

# URL completa del endpoint de Graph API para enviar mensajes
'''
Es la URL a la que hacemos POST cuando queremos responderle al usuario.
Tiene la forma: https://graph.facebook.com/v21.0/{phone_number_id}/messages
Se configura en el .env por si en el futuro cambia la version de la API.
'''
META_API_URL = os.getenv("META_API_URL")

# ID del numero de telefono asignado por Meta
'''
No es el numero en si (ej: +54911...), es un ID interno de Meta (ej: "123456789012345").
Por ahora no lo usamos directamente, pero lo dejamos cargado para etapas futuras.
'''
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")


# === SERVIDOR ===

# Puerto donde escucha Flask
'''
Render asigna el puerto via env var PORT. Si no esta definido (corriendo local), usamos 5000.
int() convierte el string del env var a numero entero.
'''
PORT = int(os.getenv("PORT", 5000))

# Entorno (development / production)
'''
Lo usamos para decidir si activar el modo debug de Flask (muestra errores detallados)
o desactivarlo en produccion (por seguridad).
'''
FLASK_ENV = os.getenv("FLASK_ENV", "development")


# === VALIDACION DE CONFIGURACION ===

def validar_configuracion():
    '''
    Chequea que todas las variables criticas esten definidas.
    Si falta alguna, levanta un error claro AL ARRANCAR el servidor en vez
    de fallar misteriosamente cuando llega el primer mensaje.

    Llamar esta funcion al inicio de app.py garantiza que el servidor no levante
    si hay un problema de configuracion.
    '''
    # Lista de variables obligatorias para que el bot funcione
    requeridas = {
        "META_VERIFY_TOKEN": META_VERIFY_TOKEN,
        "META_ACCESS_TOKEN": META_ACCESS_TOKEN,
        "META_API_URL": META_API_URL,
    }

    # Filtramos las que estan vacias o no definidas
    faltantes = [nombre for nombre, valor in requeridas.items() if not valor]

    # Si hay alguna faltante, levantamos un error con mensaje claro
    if faltantes:
        raise ValueError(
            f"Faltan variables de entorno requeridas: {', '.join(faltantes)}. "
            f"Reviza el archivo .env o las env vars de Render."
        )
