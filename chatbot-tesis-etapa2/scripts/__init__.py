# Marca esta carpeta como un PAQUETE de Python.
'''
Sin este archivo, los scripts no podrian importar modulos del proyecto
con "from database.connection import engine".

Esta carpeta contiene tareas que corres A MANO, no como parte del servidor:
- crear_tablas.py: crea las tablas en la BD (corres una sola vez por entorno).
- (Etapa 3) cargar_documentos.py: indexa PDFs en la vector DB.
'''
