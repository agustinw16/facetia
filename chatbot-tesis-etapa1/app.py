# Entrypoint del servidor Flask.
'''
Este archivo es DELIBERADAMENTE FINO: solo define las rutas HTTP y delega
la logica a los modulos correspondientes (whatsapp/webhook.py, etc.).

Asi cualquiera que abra el proyecto y mire este archivo entiende en 5 segundos:
"ah, las URLs disponibles son /whatsapp (GET y POST) y /health".

Toda la logica de negocio (parsear mensajes, llamar a Meta, etc.) vive en otros archivos.
'''


# Importacion de modulos
'''
Flask: framework web. Usamos la clase Flask para crear la app y los decoradores @app.route
       para mapear URLs a funciones Python.
config: nuestro modulo de configuracion. Lo importamos al inicio para que:
        1) cargue las variables de .env (load_dotenv() se ejecuta al importar config).
        2) validemos la configuracion antes de arrancar.
whatsapp.webhook: importamos las dos funciones que manejan el webhook
                  (handshake GET y procesamiento POST).
'''
from flask import Flask
import config
from whatsapp.webhook import verificar_webhook, procesar_mensaje_entrante


# Validar la configuracion ANTES de levantar el servidor.
'''
Si falta alguna variable de entorno critica (META_ACCESS_TOKEN, etc.), preferimos
fallar AL ARRANCAR con un error claro, en vez de fallar cuando llegue el primer mensaje
y dejarte sin saber por que.
'''
config.validar_configuracion()


# Crear la instancia de la app Flask.
'''
__name__ es una variable especial de Python que vale "app" si este archivo se ejecuta
como modulo principal. Flask la usa para resolver rutas relativas (templates, static, etc.).
'''
app = Flask(__name__)


# === RUTA 1: GET /whatsapp (handshake de Meta) ===
@app.route("/whatsapp", methods=["GET"])
def ruta_verificar_webhook():
    '''
    Cuando Meta configura el webhook por primera vez, hace GET aca con un challenge.
    La logica vive en whatsapp/webhook.py, este archivo solo conecta la URL con la funcion.
    '''
    return verificar_webhook()


# === RUTA 2: POST /whatsapp (mensajes de usuarios) ===
@app.route("/whatsapp", methods=["POST"])
def ruta_procesar_mensaje():
    '''
    Cuando un usuario envia un mensaje al numero del bot, Meta hace POST aca
    con el contenido del mensaje. Delegamos a whatsapp/webhook.py.
    '''
    return procesar_mensaje_entrante()


# === RUTA 3: GET /health (chequeo de salud) ===
@app.route("/health", methods=["GET"])
def ruta_health():
    '''
    Endpoint simple para verificar que el servidor esta vivo.
    Sirve para:
    - Render: chequear que el deploy funciona.
    - UptimeRobot (en Etapa 6): pingear cada 5 min para evitar el cold start.
    - Vos: probar que la app levanto correctamente sin tener que mandar un mensaje real.
    '''
    return {"status": "ok", "etapa": 1}, 200


# === ARRANQUE DEL SERVIDOR (solo para desarrollo local) ===
'''
if __name__ == "__main__" hace que este bloque se ejecute SOLO cuando corres
"python app.py" directamente, NO cuando gunicorn importa la app en produccion.

En PRODUCCION (Render): gunicorn levanta el servidor con "gunicorn app:app",
ignorando este bloque.

En DESARROLLO (local): "python app.py" usa el servidor de desarrollo de Flask,
que tiene debug=True para ver errores detallados y autorecarga al cambiar archivos.
'''
if __name__ == "__main__":
    # host="0.0.0.0" permite conexiones desde fuera de localhost (necesario para ngrok, Render, etc.).
    # debug=True solo si estamos en development (config controla esto via FLASK_ENV).
    app.run(
        host="0.0.0.0",
        port=config.PORT,
        debug=(config.FLASK_ENV == "development")
    )
