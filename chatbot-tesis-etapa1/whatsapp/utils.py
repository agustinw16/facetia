# Modulo de funciones utilitarias relacionadas a WhatsApp.
'''
Aca van las funciones de ayuda que no tienen que ver directamente con el webhook
ni con el envio de mensajes, pero que sirven a ambos. Ejemplo: formateo de numeros.

En la Etapa 4 (seguridad) vamos a agregar aca tambien la funcion validar_firma_meta()
para verificar el header X-Hub-Signature-256.
'''


def formatear_numero(numero):
    '''
    Quita el "9" extra de los celulares argentinos para que Meta los reconozca.

    Contexto del problema:
    En Argentina, cuando alguien escribe desde su celular, WhatsApp manda el numero
    con un "9" extra despues del codigo de pais (ej: 5493815887766).
    Pero la API de Meta espera el numero SIN ese 9 (ej: 543815887766) para responder.
    Si no quitamos el 9, el mensaje de respuesta nunca llega al usuario.

    Esta funcion es la misma que tenias en tu app.py original, solo mudada a este archivo.

    Parametros:
        numero: string con el numero recibido de Meta (ej: "5493815887766").

    Devuelve:
        string con el numero formateado (ej: "543815887766"), o el numero original
        si no necesita formateo (ej: usuarios de otros paises).
    '''
    # Si viene en formato 549... y tiene 13 digitos (codigo pais 54 + 9 + 10 digitos)
    if numero.startswith("549") and len(numero) == 13:
        # Convertir 5493815887766 -> 543815887766
        # numero[3:] toma desde el caracter en posicion 3 hasta el final, salteandose el "9"
        return "54" + numero[3:]

    # Si no cumple la condicion (ej: numero de Brasil, de USA, etc.), lo devolvemos tal cual
    return numero
