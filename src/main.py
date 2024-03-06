# PENDIENTES
# 1. Revisar las rutas de los archivos (.env y resources) que estan definidas relativamente.
#    Deben llevarse a rutas globales con base en variables de entorno
# 2. Agregar timestamps a los sent_messages
# 3. Parametrizar el manejo de los tiempos de valides de eventos (notificaciones y activacion tickets)

from dotenv import load_dotenv
import os

from fastapi import FastAPI, Depends, Query, Request, HTTPException

from pydantic import BaseModel
from typing import Annotated, List
from enum import Enum

import psycopg

from jose import JWTError, jwt

from datetime import datetime, timedelta
import pytz

from utilities.notifications import MovieNotificationsHandler
from utilities import wa, graphics

load_dotenv( "./config/.env" )

CONN_URL = os.environ.get( "CONN_URL" )

WA_VERIFY_TOKEN = os.environ.get( "WA_VERIFY_TOKEN" )
WA_ACCOUNT_ID = os.environ.get( "WA_ACCOUNT_ID" )

SECRET_KEY = os.environ.get( "SECRET_KEY" )
ALGORITHM = "HS256"



MovieNotificationsHandler().start()
app = FastAPI()



class BusinessUser( BaseModel ):
    user_id: int
    user_type: str
    comp_id: int
    user_role: str

def decode_token( access_token: str ) -> BusinessUser:
    try:
        return BusinessUser( **jwt.decode( access_token, SECRET_KEY, algorithms = [ ALGORITHM ] ) )
    
    except JWTError:
        raise HTTPException(
            status_code = 401,
            detail = "Invalid access token"
        )



class EventStateEnum( str, Enum ):
    pending_confirm = "PENDING_CONFIRM"
    never_confirmed = "NEVER_CONFIRMED"
    confirmed = "CONFIRMED"
    canceled = "CANCELED"

@app.post( "/reservations/confirm" )
async def send_reservation_confirmation(
    event_type: Enum,
    phone: str,
    fields: dict,

    user: Annotated[ BusinessUser, Depends( decode_token ) ]
):
    if( event_type == "MOVIE" ):
        response = wa.send_movie_reservation_confirmation( phone, fields )
        
        if( response.status_code != 200 ):
            raise HTTPException( status_code = 500 )



@app.get( "/webhook" )
async def webhook_verification(
    hub_mode: str = Query( alias = "hub.mode" ),
    hub_challenge: int = Query( alias = "hub.challenge" ),
    hub_verify_token: str = Query( alias = "hub.verify_token" )
) -> int:
    if( hub_mode == "subscribe" and hub_verify_token == WA_VERIFY_TOKEN ):
        return hub_challenge
    else:
        raise HTTPException( status_code = 403 )



def get_message_type( cur, wamid ):
    cur.execute(
        f"""
        select sm.message_type
        from whatsapp.sent_messages sm
        where sm.wamid = '{ wamid }'
        """
    )

    return cur.fetchone()[ 0 ]

def get_reservation( cur, wamid ):
    cur.execute(
        f"""
        select r.reserv_id, me.movie_name, e.event_date
        from whatsapp.sent_messages sm, logistics.reservation r, logistics.movie_event me, logistics.event e
        where sm.reserv_id = r.reserv_id
        and r.event_id = me.event_id
        and r.event_id = e.event_id
        and sm.wamid = '{ wamid }'
        and r.reserv_state = 'CONFIRMED'
        """
    )

    return cur.fetchone()

def event_window_active( cur, reserv_id ):
    cur.execute(
        f"""
        select count(*)
        from logistics.reservation r, logistics.event e, logistics.venue v, logistics.location l
        where r.event_id = e.event_id
        and e.venue_id = v.venue_id
        and v.loc_id = l.loc_id
        and r.reserv_id = '{ reserv_id }'
        and current_timestamp at time zone 'UTC' >= e.event_date - interval '1 minute' * l.utc_offset - interval '60 minutes'
        and current_timestamp at time zone 'UTC' <= e.event_date - interval '1 minute' * l.utc_offset + interval '15 minutes'
        """
    )

    return cur.fetchone()

def get_non_activated_valid_tickets( cur, reserv_id ):
    cur.execute(
        f"""
        select t.ticket_id, t.ticket_num
        from logistics.reservation r, logistics.ticket t, logistics.active_ticket at
        where r.reserv_id = t.reserv_id
        and t.ticket_id = at.ticket_id
        and r.reserv_id = { reserv_id }
        and t.state_type = 'VALID'
        and (
            at.valid_until is null
            or current_timestamp at time zone 'UTC' > at.valid_until
        )
        """
    )
    return cur.fetchall()

@app.post( "/webhook" )
async def webhook_handler( request: Request ):
    data = await request.json()

    obj = data.get( "object" )
    if( obj != "whatsapp_business_account" ):
        raise HTTPException( status_code = 422 )

    entry = data.get( "entry" )
    if( not entry ):
        return

    wa_id = entry[ 0 ].get( "id" )
    if( wa_id != WA_ACCOUNT_ID ):
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
        response = wa.send_default_message( message[ "from" ] )

        if( response.status_code != 200 ):
            raise HTTPException( status_code = 500 )

        return

    wamid = context.get( "id" )

    with psycopg.connect( CONN_URL ) as conn:
        with conn.cursor() as cur:
            mess_type = get_message_type( cur, wamid )

            if( mess_type == "TICKETS_AVAIL_NOTIF" or mess_type == "TICKETS" ):
                button_text = message[ "button" ][ "text" ]

                # Revisar. Llevar a template pero creada por api. Mejor control de button id
                if( button_text == "Activar entradas" ):
                    reserv = get_reservation( cur, wamid )

                    if( not reserv ):
                        # Enviar mensaje indicando que no se encontro la reserva
                        return
                    
                    reserv_id, movie_name, movie_date = reserv

                    if( not event_window_active( cur, reserv_id ) ):
                        # Enviar mensaje indicando que el evento ya no esta activo
                        return
                    
                    non_act_valid_tickets = get_non_activated_valid_tickets( cur, reserv_id )

                    if( not len( non_act_valid_tickets ) ):
                        # Enviar mensaje indicando que no hay tickets que se puedan activar
                        return
                    
                    response = wa.send_movie_tickets_activation( message[ "from" ], len( non_act_valid_tickets ) )

                    if( response.status_code != 200 ):
                        print( response.text )
                        raise HTTPException( status_code = 500 )

                    wamid = response.json()[ "messages" ][ 0 ][ "id" ]

                    cur.execute(
                        f"""
                        insert into whatsapp.sent_messages(wamid, reserv_id, message_type, sent_to) values(
                            '{ wamid }',
                            { reserv_id },
                            'TICKETS_ACT',
                            '{ message[ "from" ] }'
                        )
                        """
                    )
                    
            elif( mess_type == "TICKETS_ACT" ):
                reserv = get_reservation( cur, wamid )

                if( not reserv ):
                    # Enviar mensaje indicando que no se encontro la reserva
                    return
                
                reserv_id, movie_name, movie_date = reserv

                if( not event_window_active( cur, reserv_id ) ):
                    # Enviar mensaje indicando que el evento ya no esta activo
                    return
                
                non_act_valid_tickets = get_non_activated_valid_tickets( cur, reserv_id )

                if( not len( non_act_valid_tickets ) ):
                    # Enviar mensaje indicando que no hay tickets que se puedan activar
                    return

                num_tickets = int( message[ "interactive" ][ "list_reply" ][ "id" ] )

                # PARAMETRIZAR EL ACT_SPAN
                valid_until = ( datetime.now( pytz.utc ) + timedelta( minutes = 3 ) ).strftime( "%Y-%m-%d %H:%M:%S" )
                
                graphics.create_movie_tickets_pdf(
                    [ ( ticket_id, movie_name, movie_date.strftime( "%Y-%m-%d %H:%M:%S" ), ticket_num ) for ticket_id, ticket_num in non_act_valid_tickets[ :num_tickets ] ],
                    valid_until
                )

                cur.execute(
                    f"""
                    update logistics.active_ticket
                    set valid_until = '{ valid_until }'
                    where ticket_id in { "(" + "".join( [ str( ticket_id ) + ", " for ticket_id, _ in non_act_valid_tickets[ :num_tickets ] ] )[ :-2 ] + ")" }
                    """
                )

                response = wa.upload_movie_ticket()

                # Dar mejor manejo al error. Probar reintento de envio de mensaje?
                if( response.status_code != 200 ):
                    cur.execute(
                        f"""
                        update logistics.active_ticket
                        set valid_until = null
                        where ticket_id = { "(" + "".join( [ str( ticket_id ) + ", " for ticket_id, _ in non_act_valid_tickets[ :num_tickets ] ] )[ :-2 ] + ")" }
                        """
                    )

                    raise HTTPException( status_code = 500 )

                rid = response.json()[ "id" ]

                response = wa.send_movie_ticket( message[ "from" ], rid )

                # Dar mejor manejo al error. Probar reintento de envio de mensaje?
                if( response.status_code != 200 ):
                    cur.execute(
                        f"""
                        update logistics.active_ticket
                        set valid_until = null
                        where ticket_id = { "(" + "".join( [ str( ticket_id ) + ", " for ticket_id, _ in non_act_valid_tickets[ :num_tickets ] ] )[ :-2 ] + ")" }
                        """
                    )

                    raise HTTPException( status_code = 500 )
                
                wamid = response.json()[ "messages" ][ 0 ][ "id" ]

                cur.execute(
                    f"""
                    insert into whatsapp.sent_messages(wamid, reserv_id, message_type, sent_to) values(
                        '{ wamid }',
                        { reserv_id },
                        'TICKETS',
                        '{ message[ "from" ] }'
                    )
                    """
                )

    return
