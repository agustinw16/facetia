# Script para crear las tablas en la BD (corres a mano, una vez por entorno).
'''
Como se usa:

LOCAL (con SQLite):
    cd chatbot-tesis-etapa2
    .\venv\Scripts\activate
    python -m scripts.crear_tablas

    Resultado: se crea el archivo "chatbot.db" en la raiz del proyecto con
    las tablas vacias.

RENDER (con Postgres):
    Opcion A - Shell de Render:
      Dashboard -> tu servicio web -> "Shell" -> ejecutar:
          python -m scripts.crear_tablas

    Opcion B - desde tu PC apuntando a Render:
      Copiar la URL externa de la BD de Render en tu .env local como DATABASE_URL,
      correr el script, y volver a tu URL local.

NOTA IMPORTANTE: SQLAlchemy "create_all" es IDEMPOTENTE:
- Si la tabla NO existe, la crea.
- Si la tabla YA existe, no hace nada (no rompe ni borra datos).
- Si una columna fue agregada al modelo, NO la agrega (eso es trabajo de "Alembic",
  herramienta de migraciones que veremos en etapa 5 si hace falta).

Por que un script aparte y no auto-crearlas al arrancar la app:
- Crear tablas es una operacion de "infrastructure", no de "request".
- Hacerlo en el arranque hace que cada deploy a Render abra una transaccion DDL,
  lo cual puede fallar bajo carga concurrente.
- Asi vos controlas CUANDO se modifica el esquema.
'''


# Importacion de modulos
'''
Importamos el engine y la Base de connection.py.
Importar models.py es CRITICO aunque no usemos sus clases directamente:
los modelos se registran en Base.metadata al ser IMPORTADOS. Si no importamos
models.py, Base.metadata estaria vacio y create_all() no crearia nada.
'''
from database.connection import engine, Base
from database import models  # noqa: F401  (importacion necesaria para registrar modelos)


def main():
    '''
    Crea TODAS las tablas registradas en Base.metadata.
    Idempotente: si ya existen, no las recrea.
    '''
    print("Creando tablas...")
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas correctamente.")

    # Mostrar las tablas creadas para confirmar.
    # engine.dialect.get_table_names funciona en SQLite y Postgres.
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tablas = inspector.get_table_names()
    print(f"Tablas en la BD: {tablas}")


if __name__ == "__main__":
    main()
