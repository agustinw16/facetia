# Funciones de alto nivel para operaciones contra la BD.
'''
Este archivo aplica el patron REPOSITORY: en vez de que webhook.py escriba SQL/SQLAlchemy
directamente, llama a funciones expresivas tipo "obtener_o_crear_usuario(telefono)".

Beneficios:
1) webhook.py no se llena de detalles de ORM (mas legible).
2) Si mañana cambiamos de SQLAlchemy a otro ORM, solo se toca este archivo.
3) Cada funcion es testeable de forma aislada.

Convencion: TODAS las funciones reciben una "sesion" como argumento.
Quien llama (webhook.py) es responsable de abrir y cerrar la sesion.
Asi varias operaciones pueden compartir la MISMA transaccion.
'''


# Importacion de modulos
'''
datetime: para actualizar ultimo_visto del usuario.
timedetal: permite calcular la diferencia entre dos fechas
.models: las clases Usuario y Mensaje definidas en models.py.
'''
from datetime import datetime, timedelta
from .models import Usuario, Mensaje
import config


def obtener_o_crear_usuario(sesion, telefono):
    '''
    Busca un usuario por su telefono. Si no existe, lo crea.

    Patron muy comun: "upsert" (update or insert). En vez de tener que chequear
    antes y crear despues, encapsulamos esa logica aca.

    Tambien actualizamos ultimo_visto a "ahora" porque sabemos que el usuario
    acaba de escribir.

    Parametros:
        sesion: sesion SQLAlchemy abierta (la pasa el llamador).
        telefono: numero del usuario (string, ya formateado sin "+").

    Devuelve:
        instancia de Usuario (existente o recien creada).
    '''
    # Buscamos al usuario por telefono. .first() devuelve la primera fila o None.
    usuario = sesion.query(Usuario).filter(Usuario.telefono == telefono).first()

    if usuario is None:
        # Usuario nuevo: lo creamos
        usuario = Usuario(telefono=telefono)
        sesion.add(usuario)
        # sesion.flush() hace el INSERT pero no hace commit (se guarda temporalmente, la transacción todavía no está confirmada.). 
        # Asi obtenemos el ID autogenerado antes de continuar.
        sesion.flush()
        print(f"[REPO] Usuario nuevo creado: telefono={telefono}, id={usuario.id}")
    else:
        # Usuario existente: actualizamos su ultimo_visto
        usuario.ultimo_visto = datetime.utcnow()

    return usuario


def ya_fue_procesado(sesion, message_id_meta):
    '''
    Verifica si ya recibimos y procesamos este message_id antes.

    Uso CRITICO para deduplicacion: si Meta/Twilio tienen un timeout y reintentan
    el mismo mensaje, sin esta funcion responderiamos dos veces al usuario.

    Parametros:
        sesion: sesion SQLAlchemy abierta.
        message_id_meta: el ID que Meta o Twilio dieron al mensaje entrante.

    Devuelve:
        True si ya esta en la BD, False si es nuevo.
    '''
    if not message_id_meta:
        # Si no hay ID (raro), no podemos deduplicar; tratamos como nuevo.
        return False

    # query().filter().first() es la forma estandar de buscar.
    # Devolvemos True si encontramos alguno, False si no.
    existente = sesion.query(Mensaje).filter(
        Mensaje.message_id_meta == message_id_meta
    ).first()

    return existente is not None


def guardar_mensaje_entrante(sesion, usuario_id, message_id_meta, texto, estado="recibido"):
    '''
    Persiste en la BD un mensaje que recibimos del usuario.

    Parametros:
        sesion: sesion SQLAlchemy abierta.
        usuario_id: ID del usuario que envio el mensaje (debe existir en usuarios).
        message_id_meta: ID que dio Meta o Twilio (sirve para dedup).
        texto: contenido del mensaje.
        estado: "recibido" (default). Usar "rechazado_largo" para mensajes
                que se cortaron por el limite de largo, asi obtener_historial()
                los puede excluir de la memoria conversacional.

    Devuelve:
        instancia de Mensaje recien creada.
    '''
    mensaje = Mensaje(
        usuario_id=usuario_id,
        direccion="entrante",
        message_id_meta=message_id_meta,
        texto=texto,
        estado=estado,
    )
    sesion.add(mensaje)
    sesion.flush()
    return mensaje


def guardar_mensaje_saliente(sesion, usuario_id, texto, estado="enviado"):
    '''
    Persiste en la BD un mensaje que nosotros enviamos como respuesta.

    A diferencia del entrante, no tenemos message_id_meta al momento de enviarlo
    (en realidad Meta nos lo devuelve, pero por simplicidad no lo capturamos en esta etapa).

    Parametros:
        sesion: sesion SQLAlchemy abierta.
        usuario_id: ID del usuario destinatario.
        texto: contenido de la respuesta.
        estado: "enviado" (default), "fallido", etc.

    Devuelve:
        instancia de Mensaje recien creada.
    '''
    mensaje = Mensaje(
        usuario_id=usuario_id,
        direccion="saliente",
        message_id_meta=None,
        texto=texto,
        estado=estado,
    )
    sesion.add(mensaje)
    sesion.flush()
    return mensaje

def obtener_historial(sesion, usuario_id, limite=None, ventana_minutos=None):
    '''
    Devuelve los ultimos mensajes de la conversacion de un usuario, en orden
    cronologico (del mas viejo al mas nuevo).

    Se usa para darle MEMORIA al bot: estos mensajes se le pasan al LLM junto
    con la pregunta actual, asi entiende preguntas que dependen del contexto
    previo ("y cuanto dura?", "y las materias?").

    Parametros:
        sesion: sesion SQLAlchemy abierta.
        usuario_id: ID del usuario del que queremos el historial.
        limite: cuantos mensajes traer. Si es None, usa config.MEMORIA_MAX_MENSAJES.
        ventana_minutos: cuanto tiempo hacia atras mirar. Si es None, usa
                         config.MEMORIA_VENTANA_MINUTOS.

    Devuelve:
        lista de dicts {"rol": "usuario"|"bot", "texto": "..."}.
        Lista vacia si el usuario no tiene mensajes recientes.
    '''
    # Mismo patron que vector_db.buscar_similares(): si no nos pasan el valor,
    # lo leemos de config. Asi las llamadas quedan cortas.
    if limite is None:
        limite = config.MEMORIA_MAX_MENSAJES
    if ventana_minutos is None:
        ventana_minutos = config.MEMORIA_VENTANA_MINUTOS

    # Calculamos desde que momento contar. Usamos utcnow(Devuelve la fecha y hora UTC actuales) porque los modelos
    # guardan creado_en con datetime.utcnow (ver models.py).
    desde = datetime.utcnow() - timedelta(minutes=ventana_minutos)

    # Saco de la base de datos los ultimos mensajes
    filas = (
        sesion.query(Mensaje)
        .filter(Mensaje.usuario_id == usuario_id)
        .filter(Mensaje.creado_en >= desde)
        # Los mensajes con estado "fallido" nunca le llegaron al usuario,
        # asi que no forman parte de la conversacion que el vivio.
        .filter(Mensaje.estado != "fallido")
        # Los "rechazado_largo" fueron cortados por el limite de largo: no
        # son intercambios reales, no deben contaminar la memoria del LLM.
        .filter(Mensaje.estado != "rechazado_largo")
        # Ordenamos del MAS NUEVO al mas viejo y cortamos: asi el limite
        # se queda con los ULTIMOS N, no con los primeros N.
        .order_by(Mensaje.creado_en.desc())
        .limit(limite)
        .all()
    )

    # Los dimos vuelta para poder limitar; ahora los reordenamos cronologicamente,
    # que es como el LLM espera leer una conversacion.
    filas.reverse()

    # Traducimos de "lenguaje de base de datos" (entrante/saliente) a un
    # lenguaje neutro (usuario/bot). Asi chatbot/llm.py NO necesita saber como
    # se llaman las columnas de la BD, y se mantiene la separacion de capas.
    return [
        {
            "rol": "usuario" if fila.direccion == "entrante" else "bot",
            "texto": fila.texto,
        }
        for fila in filas
    ]
