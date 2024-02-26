from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import requests

import json

app = FastAPI()

VERIFY_TOKEN = "HAPPY"
ACCESS_TOKEN = "EAAE53IcQ5pQBO0ZBTLLTO16r2ZBuy7ZBDiAgnGsNzCUbM4RysRLsFvNWxwvTZAUaAT24ZCor4fZCnvn82HKKJmH9eVGx3vdYkPHj1lcHYkIE4uby0ycCIqKivd9oqFWlJKpbX8R9uy0t4vuZBwOTcwzMLdhow5w2kS9EitCeNZBZBRNZAON9dhUaRYTJoTgwZCJ4qZBeW4tTNdB9Jjks2PWPUAZDZD"


@app.post( "/webhook" )
async def webhook_handler( request: Request ):
    data = await request.json()

    if( data.get( "object" ) and data.get( "entry" ) ):
        changes = data[ "entry" ][ 0 ].get( "changes", [] )
        if( changes and changes[ 0 ].get( "value" ) ):
            phone_number_id = changes[ 0 ][ "value" ][ "metadata" ][ "phone_number_id" ]
            from_number = changes[ 0 ][ "value" ][ "messages" ][ 0 ][ "from" ]
            msg_body = changes[ 0 ][ "value" ][ "messages" ][ 0 ][ "text" ][ "body" ]

            response = requests.post(
                f"https://graph.facebook.com/v12.0/{phone_number_id}/messages?access_token={ACCESS_TOKEN}",
                json = {
                    "messaging_product": "whatsapp",
                    "to": from_number,
                    "text": json.dumps( { "body": msg_body } )
                },
                headers = { "Content-Type": "application/json" }
            )

            response.raise_for_status()

@app.get( "/webhook" )
async def verify_webhook_mode( request: Request ):
    mode = request.query_params.get( "hub.mode" )
    token = request.query_params.get( "hub.verify_token" )
    challenge = request.query_params.get( "hub.challenge" )

    if( mode == "subscribe" and token == VERIFY_TOKEN ):
        return JSONResponse( content=challenge, status_code=200 )
    else:
        raise HTTPException( status_code = 403 )
