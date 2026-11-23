# Modulo de FERIADOS: trae los feriados nacionales de Argentina desde una fuente oficial.
'''
QUE HACE ESTE ARCHIVO:
Descarga la lista de feriados nacionales del año en curso (dataset oficial del
Ministerio del Interior, publicado en datos.gob.ar y servido como JSON publico, sin
clave) y arma un texto con los que caen dentro de los proximos 14 dias, listo para
sumarlo a las instrucciones de la IA.

Fuente: https://datos.gob.ar/ar/dataset/feriados-nacionales1 (dataset "Feriados
Nacionales"). El archivo del año sigue el patron
https://www.argentina.gob.ar/sites/default/files/holidays-{anio}-es.json

POR QUE ESTO Y NO SOLO LA PLANILLA DE AVISOS:
Los feriados nacionales (25 de mayo, dia de la independencia, etc.) ya estan definidos
por ley: no tiene sentido cargarlos a mano en la planilla de avisos, y es facil
olvidarse de alguno. Lo que SI sigue yendo en la planilla son los eventos propios de
la facultad (paro, receso, cierre administrativo), que ninguna API conoce.

POR QUE UNA VENTANA DE 14 DIAS (y no el año completo):
Si le pasaramos TODO el año en cada consulta, "ensuciariamos" las instrucciones con
feriados que todavia faltan meses: mas tokens gastados sin necesidad. Con 14 dias
alcanza para responder "mañana", "esta semana" y "la semana que viene", que es donde
la pregunta "¿hay feriado?" tiene sentido real. Si preguntan por una fecha mas lejana,
el bot no va a tener el dato (igual que hoy no lo tiene para nada que no sea RAG/avisos).

POR QUE EL CACHE DURA HORAS (y no minutos, como los avisos):
Los feriados no cambian de un momento a otro como un aviso de ultimo momento. Alcanza
con refrescar la lista una vez por dia para no golpear la API en cada mensaje.
'''


# Importacion de modulos
'''
time: para medir cuanto paso desde la ultima descarga.
threading: un candado (Lock) para que dos mensajes simultaneos no descarguen a la vez.
datetime.date/timedelta: para armar y comparar fechas.
requests: para descargar la lista de feriados.
fecha: para saber que dia es hoy en Argentina.
'''
import time
import threading
from datetime import date, timedelta
import requests
from . import fecha


# Direccion del JSON oficial de feriados de Argentina. {anio} se reemplaza al pedirla.
API_FERIADOS = "https://www.argentina.gob.ar/sites/default/files/holidays-{anio}-es.json"

# Cada cuantas horas se vuelve a descargar la lista del año.
CACHE_HORAS = 24

# Cuantos dias hacia adelante (desde hoy) se le informan al LLM.
VENTANA_DIAS = 14

# Copia en memoria de los feriados del año ya descargado (variables "privadas").
_feriados_en_memoria = None   # lista de dicts {"fecha", "motivo"} del año cacheado
_anio_cacheado = None         # para volver a descargar si cruzamos de año (ej: 31/12 -> 1/1)
_momento_descarga = 0.0
_candado = threading.Lock()


def _descargar_feriados(anio):
    '''
    Descarga los feriados nacionales de un año desde el JSON oficial.

    El archivo viene en formato "schema.org" (asi lo publica el Gobierno): la lista
    de feriados no esta en la raiz del JSON, sino anidada en
    datos["mainEntity"]["itemListElement"], y cada feriado trae su fecha ya completa
    en "startDate" (formato "AAAA-MM-DD"), no separada en dia/mes.

    Devuelve:
        lista de dicts {"fecha": date, "motivo": str}.
    '''
    respuesta = requests.get(API_FERIADOS.format(anio=anio), timeout=5)
    respuesta.raise_for_status()
    datos = respuesta.json()
    items = datos["mainEntity"]["itemListElement"]
    return [
        {
            "fecha": date.fromisoformat(elemento["item"]["startDate"]),
            "motivo": elemento["item"]["name"],
        }
        for elemento in items
    ]


def _obtener_feriados():
    '''
    Devuelve los feriados del año ACTUAL, usando la copia en memoria si es reciente.

    Si cambiamos de año (ej: el bot sigue prendido del 2026 al 2027) o paso mas de
    CACHE_HORAS desde la ultima descarga, vuelve a pedirle la lista a la API.
    '''
    global _feriados_en_memoria, _anio_cacheado, _momento_descarga

    anio_actual = fecha.ahora_argentina().year

    with _candado:
        segundos_desde_descarga = time.time() - _momento_descarga
        vencido = segundos_desde_descarga > CACHE_HORAS * 3600
        if _feriados_en_memoria is None or _anio_cacheado != anio_actual or vencido:
            try:
                _feriados_en_memoria = _descargar_feriados(anio_actual)
                _anio_cacheado = anio_actual
                print(f"[FERIADOS] Lista {anio_actual} descargada: {len(_feriados_en_memoria)} feriados.")
            except Exception as e:
                # La API no respondio: seguimos con la copia anterior (si habia).
                print(f"[FERIADOS] No se pudo descargar la lista de {anio_actual}: {e}")
                if _feriados_en_memoria is None:
                    _feriados_en_memoria = []
            _momento_descarga = time.time()
        return _feriados_en_memoria


def feriados_proximos_texto():
    '''
    Funcion principal del modulo: la llama rag.py en cada consulta.

    Devuelve:
        texto con los feriados nacionales dentro de los proximos VENTANA_DIAS dias,
        o None si no hay ninguno en ese rango o si la API no respondio nunca.
    '''
    hoy = fecha.ahora_argentina().date()
    limite = hoy + timedelta(days=VENTANA_DIAS)

    proximos = [f for f in _obtener_feriados() if hoy <= f["fecha"] <= limite]
    if not proximos:
        return None

    lineas = [f"- {f['fecha']:%d/%m/%Y}: {f['motivo']}" for f in proximos]
    return "FERIADOS NACIONALES PROXIMOS (Argentina):\n" + "\n".join(lineas)
