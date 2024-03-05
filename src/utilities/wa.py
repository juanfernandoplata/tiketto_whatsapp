from dotenv import load_dotenv
import os

import requests

load_dotenv( "./config/.env" )
WA_API_VERSION = os.environ.get( "WA_API_VERSION" )
WA_NUM_ID = os.environ.get( "WA_NUM_ID" )
WA_ACCESS_TOKEN = os.environ.get( "WA_ACCESS_TOKEN" )



# Cambiar por un template
DEFAULT_MESS_TEXT = """
¡Hola! Soy el *asistente virtual de Tiketto*.
Por ahora no estoy entrenado para hacer demasiadas cosas...
*!Pero no te preocupes!* Si recibiste un *mensaje de confirmación* de tu reserva, *1 hora antes* de tu evento recibirás un nuevo mensaje con el que podrás *obtener tus entradas*.
¡Que disfrutes de tu evento!
"""

DEFAULT_MESSAGE_REQ = lambda phone: {
    "messaging_product": "whatsapp",
    "to": phone,
    "text": {
        "body": DEFAULT_MESS_TEXT
    }
}

send_default_message = lambda phone: requests.post(
    f"https://graph.facebook.com/{WA_API_VERSION}/{WA_NUM_ID}/messages?access_token={WA_ACCESS_TOKEN}",
    headers = { "Content-Type": "application/json" },
    json = DEFAULT_MESSAGE_REQ( phone )
)



MOVIE_RESERV_CONF_REQ = lambda phone, fields: {
    "messaging_product": "whatsapp",
    "to": phone,
    "type": "template",
    "template": {
        "name": "movie_reservation_confirmation",
        "language": {
            "code": "es"
        },
        "components": [
            {
                "type": "HEADER",
                "parameters": [
                    {
                        "type": "IMAGE",
                        "image": {
                            "link": f"{ fields[ 'moviePosterUrl' ] }"
                        }
                    }
                ]
            },
            {
                "type": "BODY",
                "parameters": [
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ 'movie_name' ] }"
                    },
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ 'movie_date' ] }"
                    },
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ 'movie_time' ] }"
                    },
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ 'num_tickets' ] }"
                    }
                ]
            }
        ]
    }
}

send_movie_reservation_confirmation = lambda phone, fields: requests.post(
    f"https://graph.facebook.com/{WA_API_VERSION}/{WA_NUM_ID}/messages?access_token={WA_ACCESS_TOKEN}",
    headers = { "Content-Type": "application/json" },
    json = MOVIE_RESERV_CONF_REQ( phone, fields )
)



MOVIE_TICKETS_AVAIL_REQ = lambda phone, fields: {
    "messaging_product": "whatsapp",
    "to": phone,
    "type": "template",
    "template": {
        "name": "movie_tickets_available",
        "language": {
            "code": "es"
        },
        "components": [
            {
                "type": "BODY",
                "parameters": [
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ 'movie_name' ] }"
                    },
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ 'movie_date' ] }"
                    },
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ 'act_span' ] }"
                    }
                ]
            }
        ]
    }
}

send_movie_tickets_avail_notif = lambda phone, fields: requests.post(
    f"https://graph.facebook.com/{WA_API_VERSION}/{WA_NUM_ID}/messages?access_token={WA_ACCESS_TOKEN}",
    headers = { "Content-Type": "application/json" },
    json = MOVIE_TICKETS_AVAIL_REQ( phone, fields )
)



MOVIE_TICKETS_ACTIVATION_REQ = lambda phone, section: {
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": phone,
    "type": "interactive",
    "interactive": {
        "type": "list",
        "header": {
            "type": "text",
            "text": "Selecciona el número de entradas que quieres activar..."
        },
        "body": {
            "text": "Recuerda que las entradas solo serán válidas por *3 minutos*. Si no las usas en este periodo, tendrás que *activarlas otra vez*."
        },
        "action": {
            "button": "Activar entradas",
            "sections": [ section ]
        }
    }
}

def send_movie_tickets_activation( phone, num ):
    section = {
        "title": "Activar entradas",
        "rows": [ { "id": i, "title": f"{ i }" } for i in range( 1, num + 1 ) ]
    }

    return requests.post(
        f"https://graph.facebook.com/{WA_API_VERSION}/{WA_NUM_ID}/messages?access_token={WA_ACCESS_TOKEN}",
        headers = { "Content-Type": "application/json" },
        json = MOVIE_TICKETS_ACTIVATION_REQ( phone, section )
    )



upload_movie_ticket = lambda: requests.post(
    f"https://graph.facebook.com/{WA_API_VERSION}/{WA_NUM_ID}/media?access_token={WA_ACCESS_TOKEN}",
    data = { "type": "applicaton/pdf", "messaging_product": "whatsapp" },
    files = { "file": ( "tickets.pdf", open( "./resources/graphics/tickets.pdf", "rb" ), "application/pdf" ) }
)



TICKET_MESSAGE = lambda phone, rid: {
    "messaging_product": "whatsapp",
    "to": phone,
    "type": "template",
    "template": {
        "name": "movie_tickets",
        "language": {
            "code": "es"
        },
        "components": [
            {
                "type": "HEADER",
                "parameters": [
                    {
                        "type": "DOCUMENT",
                        "document": {
                            "filename": "tickets.pdf",
                            "id": rid
                        }
                    }
                ]
            }
        ]
    }
}

send_movie_ticket = lambda phone, rid: requests.post(
    f"https://graph.facebook.com/{WA_API_VERSION}/{WA_NUM_ID}/messages?access_token={WA_ACCESS_TOKEN}",
    headers = { "Content-Type": "application/json" },
    json = TICKET_MESSAGE( phone, rid )
)

