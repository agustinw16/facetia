# Configuracion central de la conexion a la base de datos.
'''
Este archivo es el punto unico de configuracion de SQLAlchemy. Define tres cosas:

1) ENGINE: el objeto que abre la conexion fisica a la BD (Postgres o SQLite).
   Es como el "telefono" para hablar con la BD. Se crea una sola vez al arrancar.

2) SessionLocal: una FABRICA de sesiones. Una "sesion" en SQLAlchemy es una unidad
   de trabajo (similar a una "transaccion"). Cada request del webhook deberia abrir
   una nueva sesion, hacer su trabajo y cerrarla.

3) Base: la clase base de la que TODOS los modelos heredan. SQLAlchemy la usa para
   saber cuales son tus tablas cuando llamas a Base.metadata.create_all().

Por que separar estos 3 conceptos:
- El ENGINE es PESADO (abre conexiones TCP, hace pooling). Se crea UNA VEZ.
- Las SESIONES son LIVIANAS y EFIMERAS. Una por request.
- Mezclar engine + session en un solo objeto seria malo para concurrencia.
'''

'''
Usamos la libreria SQLAlchemy ya que simplifica el trabajo.

Sin SQLAlchemy habia que:

-abrir conexiones manualmente,
-escribir SQL puro,
-cerrar conexiones,
-manejar errores,
-adaptar código según cada motor,
-protegerte de SQL Injection

'''


# Importacion de modulos
'''
sqlalchemy.create_engine: crea el "telefono" hacia la BD.
sqlalchemy.orm.sessionmaker: fabrica de sesiones (configurada con el engine).
sqlalchemy.orm.declarative_base: helper para crear la clase Base de la que heredan los modelos.
config: nuestra DATABASE_URL ya normalizada.
'''
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import config


# === ENGINE ===
'''
create_engine() recibe la URL de conexion y devuelve el engine.

connect_args={"check_same_thread": False}:
  Solo aplica a SQLite. Por defecto SQLite rechaza compartir conexion entre threads,
  pero Flask + gunicorn usan multiples threads. Este flag desactiva el chequeo.
  Para Postgres no hace falta, pero lo dejamos sin causar problemas.

echo=False:
  Si lo ponemos en True, SQLAlchemy printea cada SQL que ejecuta. Util para debug,
  pero ensucia logs en produccion.
'''
# Si la URL empieza con "sqlite", agregamos el flag de threading.
# Si es Postgres, los connect_args quedan vacios.
connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    config.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)


# === SESSION FACTORY ===
'''
sessionmaker(bind=engine) crea una "clase fabrica" de sesiones usando SQLAlchemy..
Cada llamada a SessionLocal() crea una nueva sesion atada al engine.

Una Session es el objeto que usás para interactuar con la base de datos.

Con la sesión:

-hacés consultas,
-insertás datos,
-actualizás,
-eliminás,
-confirmás cambios (commit),
-revertís (rollback).

Es como una “conexión de trabajo” temporal

autocommit=False y autoflush=False son los defaults seguros:
- autocommit=False: tenes que llamar session.commit() explicitamente. Asi controlas las transacciones.
- autoflush=False: SQLAlchemy no envia queries hasta que vos digas (mas predecible).
'''
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

'''
SessionLocal = sessionmaker... NO crea una sesión todavía. Crea una plantilla/configuración para crear sesiones después.
Asi se crea una sesion real: db = SessionLocal()
'''

# === BASE PARA MODELOS ===
'''
declarative_base() crea una clase especial para modelos ORM.. Tus modelos (Usuario, Mensaje) heredan de esta.
SQLAlchemy usa esta clase para registrar todas las tablas y poder crearlas con
Base.metadata.create_all(engine).

Base contiene internamente: metadata de tablas, registro de modelos,configuraciones ORM.
'''
Base = declarative_base()


# === HELPER PARA OBTENER UNA SESION ===
def obtener_sesion():
    '''
    Devuelve una sesion nueva.

    Uso recomendado (patron context manager):

        from database.connection import obtener_sesion

        with obtener_sesion() as sesion:
            usuario = sesion.query(Usuario).first()
            # ... hacer cosas ...
            sesion.commit()

    SQLAlchemy 2.0 soporta usar la sesion como context manager directamente:
    al salir del bloque, hace commit() si todo OK, rollback() si hubo excepcion,
    y siempre close() al final.
    '''
    return SessionLocal() 

'Devuelve la sesion local creada con sessionmarker'
