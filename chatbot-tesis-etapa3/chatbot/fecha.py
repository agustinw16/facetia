# Modulo de FECHA: da la fecha y hora actual de Argentina, en español.
'''
QUE HACE ESTE ARCHIVO:
El bot necesita saber que dia es para entender "hoy", "mañana" o "esta semana",
y para decidir si un aviso sigue vigente.
POR QUE NO ALCANZA CON datetime.now():
1) El servidor de Render usa hora UTC, que esta 3 horas ADELANTADA respecto de
   Argentina. Entre las 21 y las 24 hs de Argentina, para el servidor ya es
   "mañana", y el bot diria mal el dia.
2) Los nombres de dias y meses que da Python dependen del idioma del servidor
   (en Render, ingles). Por eso los armamos con listas propias.
'''


# Importacion de modulos
'''
datetime: fecha y hora.
timezone y timedelta: para definir la zona horaria de Argentina (UTC-3).
'''
from datetime import datetime, timezone, timedelta

# Zona horaria de Argentina.
'''
Argentina usa UTC-3 todo el año: no tiene horario de verano desde 2009.
Por eso alcanza con un desfase fijo de -3 horas, sin instalar librerias extra.
Si algun dia volviera el horario de verano, este es el UNICO lugar a cambiar.
'''
ZONA_ARGENTINA = timezone(timedelta(hours=-3))

# Nombres en español. El orden importa: weekday() devuelve 0 para el lunes.
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def ahora_argentina():
    '''
    Devuelve la fecha y hora actual en Argentina (un objeto datetime).
    La usan llm.py (para armar el texto) y avisos.py (para saber que avisos estan
    vigentes).
    '''
    return datetime.now(ZONA_ARGENTINA)


def fecha_actual_texto():
    '''
    Devuelve la fecha y hora actual como texto en español, listo para la IA.
    Ej: "martes 10 de noviembre de 2026, 14:30 hs"
    '''
    ahora = ahora_argentina()
    dia_semana = DIAS[ahora.weekday()]   # weekday(): 0 = lunes ... 6 = domingo
    mes = MESES[ahora.month - 1]         # month va de 1 a 12, pero la lista arranca en 0
    return f"{dia_semana} {ahora.day} de {mes} de {ahora.year}, {ahora:%H:%M} hs"
