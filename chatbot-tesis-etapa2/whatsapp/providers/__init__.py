# Factory para instanciar el provider correcto segun la configuracion.
'''
Este archivo es el "PUNTO DE ENTRADA" del modulo providers.

La funcion obtener_provider() lee la variable de entorno WHATSAPP_PROVIDER y
devuelve la instancia correcta (MetaProvider o TwilioProvider).

El resto del codigo NUNCA importa MetaProvider o TwilioProvider directamente;
siempre usa obtener_provider() para mantener el desacoplamiento.

Patron de cache (singleton):
- La primera vez que se llama, crea la instancia y la guarda en _provider_cache.
- En llamadas siguientes, devuelve la misma instancia (no crea una nueva cada vez).
- Esto evita reinicializar el cliente HTTP de Twilio en cada request, que es lento.
'''


# Importacion de modulos
'''
config: para leer WHATSAPP_PROVIDER del entorno.
.meta y .twilio: las dos implementaciones concretas. El punto antes indica
                 "desde el mismo paquete (providers/)".
'''
import config
from .meta import MetaProvider
from .twilio import TwilioProvider


# Variable global donde cacheamos la instancia ya creada.
# El "_" al inicio es convencion Python: "esto es privado, no lo uses desde afuera".
_provider_cache = None


def obtener_provider():
    '''
    Devuelve la instancia del provider configurado en WHATSAPP_PROVIDER.

    Si es la primera llamada, crea la instancia. Si ya existe, devuelve la cacheada.
    Asi todos los requests usan el mismo objeto y no se reinicializa el SDK
    de Twilio (que tiene overhead) en cada mensaje.

    Lanza ValueError si WHATSAPP_PROVIDER tiene un valor invalido.
    '''
    global _provider_cache

    # Si ya hay una instancia cacheada, la devolvemos
    if _provider_cache is not None:
        return _provider_cache

    # Primera llamada: creamos la instancia segun el valor del .env
    nombre = config.WHATSAPP_PROVIDER

    if nombre == "meta":
        print(f"[PROVIDERS] Inicializando MetaProvider (WHATSAPP_PROVIDER={nombre})")
        _provider_cache = MetaProvider()
    elif nombre == "twilio":
        print(f"[PROVIDERS] Inicializando TwilioProvider (WHATSAPP_PROVIDER={nombre})")
        _provider_cache = TwilioProvider()
    else:
        # Si el valor es algo raro (ej: typo), fallamos con error claro
        raise ValueError(
            f"WHATSAPP_PROVIDER='{nombre}' no es valido. "
            f"Valores aceptados: 'meta' o 'twilio'."
        )

    return _provider_cache
