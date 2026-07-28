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

'''
os.getenv() puede recibir dos parámetros: os.getenv(nombre_variable, valor_por_defecto)

si nombre_variable tiene un valor usa ese, sino usa el por defecto

'''

# === SELECCION DE PROVEEDOR DE WHATSAPP ===

# Cual proveedor usar para enviar/recibir mensajes: "meta" o "twilio".
'''
Esta es la variable CLAVE del sistema multi-provider.
- "meta": usa Meta Cloud API (Graph API + webhook handshake). Lo que tenias antes.
- "twilio": usa Twilio (SDK + webhook directo sin handshake). Util para probar.

Si la variable no esta definida, asumimos "meta" como default por compatibilidad.
.lower() asegura que no falle por mayusculas (ej: "META" o "Meta" funcionan igual).
'''
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "meta").lower()


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
Este es DISTINTO al META_VERIFY_TOKEN. Lo usa el provider de Meta en el header
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


# === TWILIO ===

# Account SID de Twilio (identificador unico de tu cuenta)
'''
Se obtiene en Twilio Console (https://console.twilio.com), arriba a la derecha.
Tiene formato: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" (siempre empieza con "AC").
Es publico en si mismo (no es secreto), pero combinado con AUTH_TOKEN da acceso total
a tu cuenta, asi que lo tratamos como secreto.
'''
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

# Auth Token de Twilio (la "contrasena" para usar la API)
'''
Se obtiene en el mismo lugar que el SID, al lado. Es SECRETO TOTAL.
Cualquiera con SID+AUTH_TOKEN puede mandar mensajes desde tu cuenta y gastarte plata.
'''
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Numero "from" de WhatsApp en Twilio (sandbox o productivo)
'''
Debe tener prefijo "whatsapp:+" seguido del numero.
- Sandbox (gratis para pruebas): "whatsapp:+14155238886" (es el numero comun del sandbox).
- Productivo: el numero que alquilaste/conectaste en Twilio.

Importante: si usas sandbox, los usuarios tienen que unirse mandando "join CODIGO" antes
de poder usar el bot. El codigo lo ves en el panel de Twilio.
'''
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")


# === BASE DE DATOS RELACIONAL (NUEVO EN ETAPA 2) ===

# URL de conexion a la base de datos.
'''
SQLAlchemy soporta varios motores de BD; la URL le dice cual usar:
- sqlite:///./chatbot.db -> archivo local SQLite (default si no hay env var).
- postgresql://user:pass@host:5432/dbname -> Postgres real (Render).

Ventaja: el codigo de SQLAlchemy NO CAMBIA entre desarrollo y produccion,
solo cambia esta URL. Mismo modelo, mismo repositorio, todo igual.

Por que el default es SQLite:
- No requiere instalar nada (viene con Python).
- Crea un archivo local "chatbot.db" facil de ver con DB Browser for SQLite.
- Ideal para desarrollo y demos rapidas.

En Render se va a definir esta variable apuntando a Postgres.
'''
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chatbot.db")

# Normalizacion: Render manda "postgres://", SQLAlchemy quiere "postgresql://"
'''
Render entrega la URL de Postgres con el prefijo viejo "postgres://".
SQLAlchemy moderno (>= 1.4) NO acepta ese prefijo, exige "postgresql://".
Esto es un parche para que funcione sin tener que editar la URL manualmente
cada vez que Render te la regenera.
'''
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


# === INTELIGENCIA ARTIFICIAL / RAG (NUEVO EN ETAPA 3) ===

# API Key de OpenAI. Es el "secreto" que autentica nuestras llamadas a OpenAI.
'''
Se genera en https://platform.openai.com/api-keys y empieza con "sk-...".
Es SECRETA: cualquiera con esta key puede gastar tu saldo de OpenAI.
Por eso va en .env (local) o en las env vars de Render (produccion), NUNCA en el codigo.
'''
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Modelo de EMBEDDINGS: convierte texto en vectores.
'''
text-embedding-3-small es el modelo barato y bueno de OpenAI para embeddings.
- Devuelve vectores de 1536 dimensiones (1536 numeros por texto).
- Cuesta ~USD 0.02 por millon de tokens (centavos para una tesis).
Si en el futuro quisieras mas precision, existe text-embedding-3-large (mas caro).
'''
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Modelo LLM: genera la respuesta final en lenguaje natural.
'''
gpt-4o-mini es el modelo chico, rapido y barato de OpenAI.
- Mas que suficiente para responder FAQ academico.
- ~6-7x mas barato que Claude Haiku.
Si despues quisieras mas calidad, se cambia este string por "gpt-4o" (mas caro).
'''
OPENAI_LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")

# Carpeta donde ChromaDB guarda los vectores en disco (modo local/persistente).
'''
ChromaDB en modo local guarda todo en una carpeta. La ponemos dentro de data/processed/
para que quede separada de los documentos fuente (data/raw/).
Esta carpeta esta en .gitignore: no se versiona, se regenera corriendo cargar_documentos.py.
'''
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/processed/chroma")

# Nombre de la "coleccion" dentro de ChromaDB (similar a una "tabla" en SQL).
'''
Una coleccion agrupa vectores relacionados. Usamos una sola para todos los chunks
de la base de conocimiento de la facultad.
'''
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "conocimiento_facultad")

# Cuantos chunks (fragmentos) recuperamos por cada pregunta.
'''
"top-K": las K piezas de informacion mas parecidas a la pregunta.
- Muy pocos (K=1): podes perder contexto.
- Muchos (K=10): metes ruido y gastas mas tokens en el LLM.
K=4 es un buen equilibrio para FAQ.
'''
RAG_TOP_K = int(os.getenv("RAG_TOP_K", 4))


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
    Chequea que todas las variables criticas del PROVIDER ACTIVO esten definidas.

    Validacion CONDICIONAL: solo valida las variables del provider que vas a usar.
    Si usas Meta, no obligamos a tener TWILIO_AUTH_TOKEN definido (y viceversa).

    Llamar esta funcion al inicio de app.py garantiza que el servidor no levante
    si hay un problema de configuracion.
    '''
    # Primero validamos que WHATSAPP_PROVIDER tenga un valor aceptado
    if WHATSAPP_PROVIDER not in ("meta", "twilio"):
        raise ValueError(
            f"WHATSAPP_PROVIDER='{WHATSAPP_PROVIDER}' no es valido. "
            f"Aceptados: 'meta' o 'twilio'."
        )

    # Segun el provider activo, definimos que variables son obligatorias
    if WHATSAPP_PROVIDER == "meta":
        requeridas = {
            "META_VERIFY_TOKEN": META_VERIFY_TOKEN,
            "META_ACCESS_TOKEN": META_ACCESS_TOKEN,
            "META_API_URL": META_API_URL,
        }
    else:  # twilio
        requeridas = {
            "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
            "TWILIO_WHATSAPP_FROM": TWILIO_WHATSAPP_FROM,
        }

    # Filtramos las que estan vacias o no definidas
    faltantes = [nombre for nombre, valor in requeridas.items() if not valor]

    # Si hay alguna faltante, levantamos un error con mensaje claro
    if faltantes:
        raise ValueError(
            f"Faltan variables de entorno para WHATSAPP_PROVIDER='{WHATSAPP_PROVIDER}': "
            f"{', '.join(faltantes)}. Reviza el archivo .env o las env vars de Render."
        )

    # === NUEVO EN ETAPA 3: la IA necesita la API key de OpenAI ===
    # Sin esta key no podemos embeber ni generar respuestas, asi que la exigimos.
    if not OPENAI_API_KEY:
        raise ValueError(
            "Falta OPENAI_API_KEY. La etapa 3 (RAG) la necesita para embeddings y LLM. "
            "Generala en https://platform.openai.com/api-keys y ponela en .env o en Render."
        )

    print(f"[CONFIG] Provider activo: {WHATSAPP_PROVIDER}. Variables OK.")
    print(f"[CONFIG] LLM: {OPENAI_LLM_MODEL} | Embeddings: {OPENAI_EMBEDDING_MODEL} | top-K: {RAG_TOP_K}")
