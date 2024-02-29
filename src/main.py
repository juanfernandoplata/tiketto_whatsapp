from fastapi import FastAPI, Query, Request, HTTPException
from pydantic import BaseModel
import requests

import psycopg
import threading
from time import sleep

CONN_PARAMS = {
    "dbname": "tiketto",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

VERIFY_TOKEN = "HAPPY"

API_VERSION = "v18.0"
WA_BUSINESS_ID = "202130686324737"
WA_APP_ID = "200080546530508"
ACCESS_TOKEN = "EAAE53IcQ5pQBOxtJsTnNDpgZBguFqKAsKkCV5ZAxHzOxb8ZAdZAotv45UwkLm2Aw8Ldu2jqRkWIu36lIZCMZB5DXWr72H7sMXIEDDjMkU5Hz2X8XtiIVHL8B7cZB9MUAaQNtkdp0WtOZBSbKPoD3elf0rNrZAN1Da03JGLvCwMoZCO9u2fKLb2NaZATcW1WQMKLFMWJTDZBporaA9NPZAXDIpYQZDZD"





TICKETS_AVAILABLE = lambda phone: {
    "messaging_product": "whatsapp",
    "to": f"{ phone }",
    "type": "template",
    "template": {
        "name": "tickets_available",
        "language": {
            "code": "es"
        }
    }
}

class NotificationsHandler( threading.Thread ):
    def __init__( self ):
        super().__init__()
        self.daemon = True

    def ticketsAvailable( self ):
        with psycopg.connect( **CONN_PARAMS ) as conn:
            with conn.cursor() as cur:
                cur.execute( f"""
                    select r.reserv_id, r.phone
                    from logistics.reservation r, logistics.event e, logistics.venue v, logistics.location l
                    where r.event_id = e.event_id
                    and e.venue_id = v.venue_id
                    and v.loc_id = l.loc_id
                    and reserv_state = 'CONFIRMED'
                    and current_timestamp at time zone 'UTC' >= e.event_date - interval '1 minute' * l.utc_offset - interval '60 minutes'
                    and current_timestamp at time zone 'UTC' <= e.event_date - interval '1 minute' * l.utc_offset;
                """)

                for reserv_id, phone in cur.fetchall():
                    print( f"{ reserv_id } -- { phone }" )
                    response = requests.post(
                        f"https://graph.facebook.com/{API_VERSION}/{WA_APP_ID}/messages?access_token={ACCESS_TOKEN}",
                        json = TICKETS_AVAILABLE( phone ),
                        headers = { "Content-Type": "application/json" }
                    )

                    if( response.status_code == 200 ):
                        cur.execute( f"""
                            update logistics.reservation
                            set reserv_state = 'TICKETS_AVAIL_NOTIFIED'
                        """)

                        wamid = response.json()[ "messages" ][ 0 ][ "id" ]

                        cur.execute( f"""
                            insert into whatsapp.sent_messages(wamid, message_type, sent_to) values(
                                '{ wamid }',
                                'TICKETS_AVAILABLE_NOTIFICATION',
                                '{ phone }'
                            )
                        """)

    def run( self, *args, **kwargs ):
        while True:
            self.ticketsAvailable()

            sleep( 60 )
            print( "60 passed..." )

nh = NotificationsHandler()
nh.start()





app = FastAPI()





DEFAULT_MESS_TEXT = """
¡Hola! Soy el asistente digital de Tiketto.
Por ahora no estoy programado para hacer demasiadas cosas...
!Pero no te preocupes! Si recibiste un mensaje de confirmación de tu reserva, 1 hora antes de tu evento recibirás un nuevo mensaje con el que podrás recibir tus boletas.
¡Que disfrutes de tu evento!
"""

DEFAULT_MESSAGE = lambda phone: {
    "messaging_product": "whatsapp",
    "to": phone,
    "text": {
        "body": DEFAULT_MESS_TEXT
    }
}

MOVIE_RESERVATION_CONFIRMATION = lambda phone, fields: {
    "messaging_product": "whatsapp",
    "to": f"{ phone }",
    "type": "template",
    "template": {
        "name": "reservation",
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
                            "link": f"{ fields[ "moviePosterUrl" ] }"
                        }
                    }
                ]
            },
            {
                "type": "BODY",
                "parameters": [
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ "movieName" ] }"
                    },
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ "movieDate" ] }"
                    },
                    {
                        "type": "TEXT",
                        "text": f"{ fields[ "movieTime" ] }"
                    }
                ]
            }
        ]
    }
}

class Reservation( BaseModel ):
    eventType: str
    phone: str
    fields: dict

@app.post( "/reservations/confirm" )
async def sendReservationConfirmation(
    reserv: Reservation
):
    response = requests.post(
        f"https://graph.facebook.com/v12.0/200080546530508/messages?access_token={ACCESS_TOKEN}",
        json = MOVIE_RESERVATION_CONFIRMATION( reserv.phone, reserv.fields ),
        headers = { "Content-Type": "application/json" }
    )

    print(response.text)

    if( response.status_code != 200 ):
        raise HTTPException( status_code = 500 )





@app.get( "/webhook" )
async def webhookVerification(
    hubMode: str = Query( alias = "hub.mode" ),
    hubChallenge: int = Query( alias = "hub.challenge" ),
    hubVerifyToken: str = Query( alias = "hub.verify_token" )
) -> int:
    if( hubMode == "subscribe" and hubVerifyToken == VERIFY_TOKEN ):
        return hubChallenge
    else:
        raise HTTPException( status_code = 403 )





@app.post( "/webhook" )
async def webhookHandler( request: Request ):
    data = request.json

    obj = data.get( "object" )
    if( obj != "whatsapp_business_account" ):
        raise HTTPException( status_code = 422 )

    entry = data.get( "entry" )
    if( not entry ):
        return

    waId = entry[ 0 ].get( "id" )
    if( waId != WA_BUSINESS_ID ):
        raise HTTPException( status_code = 403 )

    changes = entry[ 0 ].get( "changes" )
    if( not changes ):
        return

    messages = changes[ 0 ][ "value" ].get( "messages" )

    if( not messages ):
        return

    message = messages[ 0 ]

    context = message.get( "context" )
    if( not context ):
        response = requests.post(
            f"https://graph.facebook.com/{API_VERSION}/{WA_APP_ID}/messages?access_token={ACCESS_TOKEN}",
            json = DEFAULT_MESSAGE( message[ "from" ] ),
            headers = { "Content-Type": "application/json" }
        )

        return

    interMessId = context.get( "id" )

    return