# Modulo de AVISOS: lee la planilla de Google con los avisos de ultimo momento.
'''
QUE HACE ESTE ARCHIVO:
Descarga la planilla de avisos (publicada como CSV), se queda con los que estan
vigentes HOY y devuelve un texto listo para sumarlo a las instrucciones de la IA.

POR QUE LOS AVISOS VAN SIEMPRE A LA IA (y no por busqueda de vectores):
Un aviso como "paro docente el miercoles" afecta preguntas que no se le parecen
(ej: "¿a que hora abre la biblioteca el miercoles?"). Si dependiera de la busqueda
por significado, podria no aparecer. Como son pocos y cortos, pasarlos siempre
cuesta practicamente nada y la IA decide cuando son relevantes.

POR QUE NO SE DESCARGA EN CADA MENSAJE (cache):
Guardamos una copia en memoria y la renovamos cada AVISOS_CACHE_MINUTOS minutos.
Asi el bot no depende de Google en cada mensaje y responde mas rapido.
Si Google no responde, seguimos usando la ultima copia que teniamos.
'''


# Importacion de modulos
'''
csv: libreria estandar de Python para leer archivos CSV (valores separados por comas).
io.StringIO: permite que csv lea un texto como si fuera un archivo.
time: para medir cuanto paso desde la ultima descarga.
threading: un candado (Lock) para que dos mensajes simultaneos no descarguen a la vez.
datetime: para convertir "05/11/2026" en una fecha que se pueda comparar.
requests: para descargar la planilla.
config: el link de la planilla y los minutos de cache.
fecha: para saber que dia es hoy en Argentina.
'''
import csv
import io
import time
import threading
from datetime import datetime
import requests
import config
from . import fecha


# Texto que encabeza los avisos en las instrucciones de la IA.
'''
Le explica a la IA que son, que prioridad tienen y CUANDO mencionarlos.
La ultima regla evita que hable del paro cuando le preguntan cuanto dura una carrera.
'''
ENCABEZADO_AVISOS = '''AVISOS VIGENTES DE LA FACULTAD:
Son comunicados oficiales y recientes. Tienen PRIORIDAD sobre cualquier otra
informacion del contexto y podes usarlos para responder aunque no aparezcan en el.
Menciona un aviso SOLO si afecta lo que el usuario pregunta o quiere hacer
(ej: si hay paro y pregunta por clases u horarios). Si no tiene relacion, no lo menciones.
'''

# Copia en memoria de la planilla (variables "privadas" del modulo, por eso el "_").
_avisos_en_memoria = None    # lista de avisos de la ultima descarga (None = nunca se descargo)
_momento_descarga = 0.0      # cuando fue la ultima descarga (segundos, segun time.time())
_candado = threading.Lock()  # evita que dos mensajes simultaneos descarguen a la vez


def _leer_fecha(texto):
    '''
    Convierte "05/11/2026" (o "5/11/2026" o "05-11-2026") en una fecha.
    Si el texto no es una fecha valida, lanza ValueError.
    '''
    texto = texto.strip().replace("-", "/")
    return datetime.strptime(texto, "%d/%m/%Y").date()


def _leer_csv(texto_csv):
    '''
    Convierte el texto CSV de la planilla en una lista de avisos.

    Espera las columnas "Aviso", "Desde" y "Hasta" (los nombres tienen que coincidir
    EXACTO con la primera fila de la planilla). La columna "Cargado por" es solo
    para control humano: el bot no la usa.

    Las filas sin texto se ignoran. Las filas con fechas invalidas se ignoran y se
    avisa en los logs, para que alguien la corrija.

    Devuelve:
        lista de dicts {"texto", "desde", "hasta"}.
    '''
    avisos = []
    # DictReader usa la primera fila como nombres de columna: cada fila es un dict.
    lector = csv.DictReader(io.StringIO(texto_csv))
    # start=2 porque la fila 1 de la planilla son los titulos.
    for numero_fila, fila in enumerate(lector, start=2):
        texto = (fila.get("Aviso") or "").strip()
        if not texto:
            continue
        try:
            desde = _leer_fecha(fila.get("Desde") or "")
            hasta = _leer_fecha(fila.get("Hasta") or "")
        except ValueError:
            print(f"[AVISOS] Fila {numero_fila} ignorada: fecha invalida (Desde/Hasta).")
            continue
        avisos.append({"texto": texto, "desde": desde, "hasta": hasta})
    return avisos


def _descargar_avisos():
    '''
    Descarga la planilla publicada y la convierte en lista de avisos.
    timeout=5: si Google tarda mas de 5 segundos, se corta (no dejamos al usuario esperando).
    '''
    respuesta = requests.get(config.AVISOS_CSV_URL, timeout=5)
    respuesta.raise_for_status()
    # "utf-8-sig" lee bien los acentos y tolera una marca invisible que a veces
    # agregan las planillas al principio del archivo.
    return _leer_csv(respuesta.content.decode("utf-8-sig"))


def _obtener_avisos():
    '''
    Devuelve TODOS los avisos de la planilla, usando la copia en memoria si es reciente.

    "global" le avisa a Python que vamos a MODIFICAR las variables del modulo
    (no crear variables nuevas dentro de la funcion).
    '''
    global _avisos_en_memoria, _momento_descarga

    with _candado:
        segundos_desde_descarga = time.time() - _momento_descarga
        if _avisos_en_memoria is None or segundos_desde_descarga > config.AVISOS_CACHE_MINUTOS * 60:
            try:
                _avisos_en_memoria = _descargar_avisos()
                print(f"[AVISOS] Planilla descargada: {len(_avisos_en_memoria)} avisos en total.")
            except Exception as e:
                # Google no respondio: seguimos con la copia anterior (si habia).
                print(f"[AVISOS] No se pudo descargar la planilla: {e}")
                if _avisos_en_memoria is None:
                    _avisos_en_memoria = []
            # Anotamos el momento aunque haya fallado: asi no reintentamos en CADA
            # mensaje (cada intento puede tardar hasta 5 segundos).
            _momento_descarga = time.time()
        return _avisos_en_memoria


def obtener_avisos_vigentes():
    '''
    Funcion principal del modulo: la llama rag.py en cada consulta.

    Devuelve:
        texto con los avisos vigentes HOY (encabezado + una linea por aviso),
        o None si no hay avisos vigentes o si la planilla no esta configurada.
    '''
    # Sin link configurado, los avisos quedan apagados.
    if not config.AVISOS_CSV_URL:
        return None

    hoy = fecha.ahora_argentina().date()
    vigentes = [a for a in _obtener_avisos() if a["desde"] <= hoy <= a["hasta"]]
    if not vigentes:
        return None

    lineas = [
        f"- {a['texto']} (vigente del {a['desde']:%d/%m/%Y} al {a['hasta']:%d/%m/%Y})"
        for a in vigentes
    ]
    return ENCABEZADO_AVISOS + "\n".join(lineas)
