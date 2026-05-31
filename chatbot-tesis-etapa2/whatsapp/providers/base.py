# Interfaz abstracta para proveedores de WhatsApp.
'''
Este archivo define el "CONTRATO" que cualquier proveedor de WhatsApp tiene que cumplir.
No tiene logica concreta: solo dice "todo proveedor debe tener estos 3 metodos con estas firmas".

Por que existe este archivo:
- El resto del codigo (webhook.py) NO sabe si esta hablando con Meta o con Twilio.
- Solo sabe que tiene un "provider" que cumple esta interfaz.
- Asi podemos cambiar de proveedor con una sola variable de entorno (WHATSAPP_PROVIDER).
- Si manana queremos agregar otro proveedor (ej: 360dialog), solo creamos un archivo nuevo
  que herede de WhatsAppProvider y listo, el resto del sistema no se entera.

Este patron se llama "Strategy Pattern" o "Provider Pattern" y es muy comun en software profesional.
Para la tesis es ORO porque demuestra desacoplamiento real.
'''


# Importacion de modulos
'''
abc: libreria estandar de Python para crear "clases abstractas".
     ABC = Abstract Base Class. @abstractmethod marca metodos que las subclases
     ESTAN OBLIGADAS a implementar (sino Python tira error al instanciar).
'''
from abc import ABC, abstractmethod


class WhatsAppProvider(ABC):
    '''
    Clase base abstracta. Cualquier proveedor concreto (MetaProvider, TwilioProvider)
    tiene que heredar de esta clase e implementar los 3 metodos marcados con @abstractmethod.

    Si alguien intenta instanciar MetaProvider() pero olvido implementar uno de los metodos,
    Python tira TypeError al arrancar, no en runtime. Es una red de seguridad.
    '''

    @abstractmethod
    def verificar_webhook(self, request):
        '''
        Maneja el "handshake" o verificacion inicial del webhook.

        Meta: hace GET con ?hub.verify_token=X&hub.challenge=Y. Hay que devolver Y si X es correcto.
        Twilio: no hace handshake (cuando configuras el webhook en el panel, ya queda activo).
                Para Twilio, este metodo simplemente devuelve "OK" para que si alguien hace GET
                a la URL no reciba un 404.

        Parametros:
            request: el objeto Request de Flask con los datos del HTTP GET.

        Devuelve:
            String con la respuesta a enviar (challenge en Meta, "OK" en Twilio),
            o una tupla (mensaje, codigo) si hay error.
        '''
        pass

    @abstractmethod
    def parsear_mensaje_entrante(self, request):
        '''
        Convierte el request HTTP entrante en un diccionario NORMALIZADO con la info del mensaje.

        Esto es CLAVE: cada proveedor manda los datos en formato distinto:
        - Meta manda JSON anidado: request.json["entry"][0]["changes"][0]["value"]["messages"][0]...
        - Twilio manda x-www-form-urlencoded: request.form["From"], request.form["Body"]

        Este metodo se encarga de las diferencias y devuelve SIEMPRE el mismo formato:

        {
            "numero": "5491112345678",      # numero del usuario, SIN prefijos
            "texto": "Hola que tal",         # contenido del mensaje
            "message_id": "wamid.xxx"        # ID unico del mensaje (para deduplicacion en etapa 2)
        }

        Si el request no es un mensaje de texto (audio, status update, etc), devuelve None.
        Asi el webhook puede ignorarlo sin romper.

        Parametros:
            request: el objeto Request de Flask con el POST entrante.

        Devuelve:
            dict con {numero, texto, message_id} o None si no se puede procesar.
        '''
        pass

    @abstractmethod
    def enviar_mensaje(self, numero, texto):
        '''
        Envia un mensaje de texto al usuario.

        Cada proveedor lo hace distinto:
        - Meta: POST a graph.facebook.com con body JSON especifico.
        - Twilio: SDK de Python que abstrae el llamado.

        Parametros:
            numero: numero del destinatario (string, formato internacional sin "+").
            texto: contenido del mensaje a enviar.

        Devuelve:
            True si se envio correctamente, False en caso de error.
        '''
        pass
