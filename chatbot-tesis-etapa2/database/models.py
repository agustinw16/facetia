# Definicion de las tablas de la BD usando SQLAlchemy ORM.
'''
En el mundo ORM, cada CLASE Python representa una TABLA de la BD.
Cada INSTANCIA de la clase representa una FILA.
Cada ATRIBUTO de la clase representa una COLUMNA.

Ventajas vs SQL crudo:
- Auto-completado en el IDE: "usuario." te muestra todos los campos.
- Errores de tipo en tiempo de desarrollo (no en runtime).
- Migracion entre motores de BD (SQLite vs Postgres) automatica.

Limitaciones:
- Queries complejas pueden ser dificiles de expresar; en esos casos uno baja a SQL crudo.
- Para una tesis de FAQ este ORM cubre el 100% de los casos.

Esquema de las tablas (Etapa 2):

USUARIOS
+----+-----------+-------------------+-------------------+
| id | telefono  | primer_visto      | ultimo_visto      |
+----+-----------+-------------------+-------------------+
| 1  | 549112... | 2026-05-17 14:30  | 2026-05-17 18:45  |
+----+-----------+-------------------+-------------------+

MENSAJES
+----+------------+-----------+------------------+----------+-------------------+----------+
| id | usuario_id | direccion | message_id_meta  | texto    | creado_en         | estado   |
+----+------------+-----------+------------------+----------+-------------------+----------+
| 1  | 1          | entrante  | wamid.XXX123     | Hola     | 2026-05-17 14:30  | recibido |
| 2  | 1          | saliente  | NULL             | Esta...  | 2026-05-17 14:30  | enviado  |
+----+------------+-----------+------------------+----------+-------------------+----------+
'''


# Importacion de modulos
'''
sqlalchemy.*: tipos de columnas y herramientas de relacion.
datetime: para los timestamps. SQLAlchemy convierte datetime de Python <-> TIMESTAMP de la BD.
.connection: nuestra Base (la clase de la que heredan los modelos). el punto indica "importá desde el directorio actual" 
'''
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .connection import Base 


class Usuario(Base):
    '''
    Representa a una persona que escribio al bot al menos una vez.

    Identificado por su numero de telefono (que es unico).
    Guardamos primer_visto y ultimo_visto para metricas basicas (cuantos usuarios nuevos
    por dia, retencion, etc.).
    '''

    # __tablename__: el nombre real de la tabla en la BD.
    # Por convencion en plural y minusculas.
    __tablename__ = "usuarios"

    # id: clave primaria autoincremental.
    # primary_key=True le dice a SQLAlchemy que es la PK; autoincrement es automatico.
    id = Column(Integer, primary_key=True, autoincrement=True)

    # telefono: el numero del usuario, normalizado (sin "+", sin espacios).
    # unique=True crea un INDICE UNICO en la BD: no puede haber dos usuarios con el mismo telefono.
    # index=True hace que las queries por telefono sean rapidas.
    # nullable=False: nunca puede ser NULL.
    telefono = Column(String(20), unique=True, nullable=False, index=True)

    # primer_visto: cuando este usuario nos escribio por primera vez.
    # default=datetime.utcnow se ejecuta al crear la fila si no le pasamos un valor.
    primer_visto = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ultimo_visto: cuando este usuario nos escribio por ultima vez.
    # Se actualiza manualmente cada vez que llega un mensaje (en repositorio.py).
    ultimo_visto = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relacion 1-a-N: un usuario tiene MUCHOS mensajes.
    # SQLAlchemy nos permite hacer "usuario.mensajes" y devuelve la lista de Mensajes asociados.
    # back_populates="usuario" conecta esta relacion con la del modelo Mensaje (bidireccional).
    # cascade="all, delete-orphan": si borras un usuario, se borran sus mensajes tambien.
    mensajes = relationship(
        "Mensaje",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        '''
        Representacion legible al hacer print(usuario). Util para debug.
        '''
        return f"<Usuario(id={self.id}, telefono={self.telefono})>"


class Mensaje(Base):
    '''
    Cada interaccion (entrante o saliente) que pasa por el bot queda guardada aca.

    Sirve para:
    - DEDUPLICACION: si Meta/Twilio reintenta un mensaje (mismo message_id_meta),
      podemos detectarlo y no procesarlo dos veces.
    - METRICAS: cuantos mensajes / dia, tiempo de respuesta promedio, etc.
    - DEBUG: ver que respondio el bot a tal usuario en tal momento.
    '''

    __tablename__ = "mensajes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # usuario_id: clave foranea que apunta a usuarios.id.
    # ForeignKey("usuarios.id") le dice a la BD que esta columna referencia a esa tabla.
    # nullable=False: todo mensaje DEBE pertenecer a un usuario.
    # index=True acelera queries del tipo "todos los mensajes del usuario X".
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    # direccion: "entrante" (lo mando el usuario) o "saliente" (lo mando el bot).
    # En vez de Enum usamos String(10) para mantener portabilidad entre SQLite y Postgres
    # (los Enums se manejan distinto entre motores).
    direccion = Column(String(10), nullable=False)

    # message_id_meta: el ID que Meta o Twilio asignan al mensaje entrante.
    # Para los mensajes salientes (que enviamos nosotros) suele ser NULL en esta etapa.
    # unique=True garantiza que no podemos guardar el MISMO mensaje entrante dos veces.
    # index=True porque vamos a buscarlo en CADA mensaje entrante para deduplicar.
    message_id_meta = Column(String(100), unique=True, nullable=True, index=True)

    # texto: el contenido del mensaje. Text en vez de String(N) para no limitar el tamano.
    texto = Column(Text, nullable=False)

    # creado_en: timestamp de cuando se inserto en la BD.
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # estado: en esta etapa simple: "recibido" / "enviado" / "fallido".
    # En etapa 4 podriamos expandirlo con "procesando", "leido", etc.
    estado = Column(String(20), nullable=False, default="recibido")

    # Relacion inversa: cada mensaje pertenece a UN usuario.
    # back_populates conecta con la relacion definida en Usuario.
    usuario = relationship("Usuario", back_populates="mensajes")

    def __repr__(self):
        '''
        Funcion para representar de forma legible al hacer print(mensaje). Util para debug.
        '''
        return f"<Mensaje(id={self.id}, dir={self.direccion}, texto={self.texto[:30]!r})>"
