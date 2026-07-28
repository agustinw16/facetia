# Marca esta carpeta como un PAQUETE de Python (importable como "database").
'''
Sin este archivo, "from database.models import Usuario" daria error porque
Python no consideraria "database" como un modulo.

Esta vacio a proposito; el contenido esta en los otros archivos:
- connection.py: configura la conexion a la BD (engine + session factory).
- models.py: define las tablas (Usuario, Mensaje) como clases Python.
- repositorio.py: funciones de alto nivel para hacer queries (obtener_o_crear_usuario, etc.).

Sin __init__.py: 

from database.connection import engine
from database.models import User

Con __init__.py:

from .connection import engine
from .models import User

Entonces después podés hacer:

from database import engine, User

'''
