from dotenv import load_dotenv
import os

import threading
from time import sleep
import psycopg
from utilities import wa

load_dotenv( "./.env" )

CONN_URL = os.environ.get( "CONN_URL" )

class MovieNotificationsHandler( threading.Thread ):
    def __init__( self ):
        super().__init__()
        self.daemon = True

    def notify_tickets_available( self ):
        with psycopg.connect( CONN_URL ) as conn:
            with conn.cursor() as cur:
                # Revisar la parametrizacion de los tiempos de notificacion
                cur.execute(
                    f"""
                    select r.phone, r.reserv_id, me.movie_name, e.event_date
                    from logistics.reservation r, logistics.movie_event me, logistics.event e, logistics.venue v, logistics.location l
                    where r.event_id = me.event_id
                    and r.event_id = e.event_id
                    and e.venue_id = v.venue_id
                    and v.loc_id = l.loc_id
                    and (
                        select count(*)
                        from whatsapp.sent_messages sm
                        where sm.reserv_id = r.reserv_id
                    ) = 0
                    and r.reserv_state = 'CONFIRMED'
                    and current_timestamp at time zone 'UTC' >= e.event_date - interval '1 minute' * l.utc_offset - interval '60 minutes'
                    and current_timestamp at time zone 'UTC' <= e.event_date - interval '1 minute' * l.utc_offset
                    """
                )

                for phone, reserv_id, movie_name, movie_date in cur.fetchall():
                    response = wa.send_movie_tickets_avail_notif(
                        phone,
                        {
                            "movie_name": movie_name,
                            "movie_date": movie_date.strftime( "%I:%M %p" ),
                            "act_span": "3"
                        }
                    )
                    
                    if( response.status_code == 200 ):
                        wamid = response.json()[ "messages" ][ 0 ][ "id" ]
                        
                        # OJO, HAY QUE ASOCIAR LA TABLA CON EVENTOS (CADA MENSAJE PERTENECE A UN EVENTO)
                        cur.execute(
                            f"""
                            insert into whatsapp.sent_messages(wamid, reserv_id, message_type, sent_to) values(
                                '{ wamid }',
                                { reserv_id },
                                'TICKETS_AVAIL_NOTIF',
                                '{ phone }'
                            )
                            """
                        )

    def run( self, *args, **kwargs ):
        while True:
            self.notify_tickets_available()
            sleep( 60 )
