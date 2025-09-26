import os
import io
import re
import textwrap
# ¡LA LÍNEA CLAVE A VERIFICAR ES ESTA!
from PIL import Image, ImageDraw, ImageFont 
from flask import Flask, render_template, request, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader

app = Flask(__name__)

# (Las funciones y rutas auxiliares no cambian)
def limpiar_nombre_archivo(texto):
    texto = texto.replace(' ', '_')
    texto = re.sub(r'[^\w-]', '', texto)
    return texto[:50]

@app.route('/')
def pagina_de_inicio():
    return render_template('index.html')

@app.route('/galeria')
def galeria():
    ruta_galeria = os.path.join('static', 'generados')
    os.makedirs(ruta_galeria, exist_ok=True)
    query = request.args.get('q', '').upper()
    lista_completa = sorted(os.listdir(ruta_galeria), reverse=True)
    if query:
        carteles_filtrados = [c for c in lista_completa if query in c.upper().replace('_', ' ')]
    else:
        carteles_filtrados = lista_completa
    return render_template('galeria.html', carteles=carteles_filtrados, search_query=query)

@app.route('/generar', methods=['POST'])
def generar_imagen():
    texto_usuario = request.form['texto'].upper()
    try:
        ruta_plantilla = 'static/plantilla.png'
        imagen = Image.open(ruta_plantilla)
        ancho_img, alto_img = imagen.size
        
        # ¡LA LÍNEA CLAVE A VERIFICAR ES ESTA!
        dibujo = ImageDraw.Draw(imagen)
        
        ruta_fuente = 'static/ARLRDBD.TTF' 
        tamaño_fuente = 250
        fuente = ImageFont.truetype(ruta_fuente, tamaño_fuente)
        
        ancho_maximo_caracteres = 20
        envoltura = textwrap.TextWrapper(width=ancho_maximo_caracteres)
        lineas = envoltura.wrap(text=texto_usuario)
        texto_final_multilinea = "\n".join(lineas)
        
        caja_texto = dibujo.multiline_textbbox((0, 0), texto_final_multilinea, font=fuente, align="center", spacing=20)
        alto_total_texto = caja_texto[3] - caja_texto[1]
        pos_y_inicial = (alto_img - alto_total_texto) / 2
        
        dibujo.multiline_text(
            (ancho_img / 2, pos_y_inicial), 
            texto_final_multilinea, 
            font=fuente, 
            fill="black", 
            anchor="ma",
            align="center",
            spacing=20
        )
        
        nombre_base = limpiar_nombre_archivo(texto_usuario)
        nombre_archivo = f"{nombre_base}.png"
        ruta_guardado = os.path.join('static', 'generados', nombre_archivo)
        contador = 1
        while os.path.exists(ruta_guardado):
            nombre_archivo = f"{nombre_base}_{contador}.png"
            ruta_guardado = os.path.join('static', 'generados', nombre_archivo)
            contador += 1
        imagen.save(ruta_guardado)
        
        img_io = io.BytesIO()
        imagen.save(img_io, 'PNG')
        img_io.seek(0)
        
        pdf_io = io.BytesIO()
        c = canvas.Canvas(pdf_io, pagesize=landscape(A4))
        ancho_pdf, alto_pdf = landscape(A4)
        c.drawImage(ImageReader(img_io), 0, 0, width=ancho_pdf, height=alto_pdf, preserveAspectRatio=True, anchor='c')
        c.showPage()
        c.save()
        pdf_io.seek(0)
        
        return send_file(pdf_io, mimetype='application/pdf', as_attachment=True, download_name=f'cartel_{nombre_base}.pdf')
    except FileNotFoundError:
        return "ERROR CRÍTICO: Asegúrate de que los archivos 'plantilla.png' y 'ARLRDBD.TTF' existen en la carpeta 'static'.", 500
    except OSError:
         return "ERROR DE FUENTE: No se pudo cargar el archivo de fuente. Asegúrate de que no esté corrupto.", 500
    except Exception as e:
        return f"Ha ocurrido un error inesperado: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)