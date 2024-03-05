from PIL import Image, ImageDraw, ImageFont
import qrcode
import json

def create_movie_tickets_pdf( tickets, valid_until ):
    i = 1
    for ticket_id, movie_name, movie_date, ticket_num in tickets:
        base = Image.open( "./utilities/resources/graphics/template.png" )

        qr = qrcode.QRCode(
            version = 1,
            box_size = 15,
            border = 0
        )

        qr.add_data( json.dumps({
            "ticket_id": ticket_id,
            "valid_until": valid_until
        }))

        qr.make( fit = True )

        qr_img = qr.make_image(
            fill_color = "#000000",
            back_color = "#ffffff"
        )

        qr_img = qr_img.resize( ( 455, 455 ) )

        base.paste( qr_img, ( 68, 188 ) )

        draw = ImageDraw.Draw( base )

        font = ImageFont.truetype( "./utilities/resources/graphics/Montserrat-Bold.otf", 42 )
        
        start = 724
        offset = 72

        draw.text( ( 60, start + 0 * offset ), movie_name, font = font, fill = "#000000" )
        draw.text( ( 60, start + 1 * offset ), movie_date, font = font, fill = "#000000" )
        draw.text( ( 60, start + 2 * offset ), f"Entrada #{ ticket_num }", font = font, fill = "#000000" )

        base.save( f"./resources/graphics/ticket{i}.png" )

        i += 1
    
    images = [
        Image.open( f"./resources/graphics/ticket{i}.png" )
        for i in range( 1, len( tickets ) + 1 )
    ]

    images[ 0 ].convert( "RGB" ).save(
        "./resources/graphics/tickets.pdf",
        resolution = 100.0,
        append_images = images[ 1: ],
        save_all = True
    )
