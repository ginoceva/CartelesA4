import os
import io
import re
from datetime import datetime
# ¡Importamos nuevas herramientas de Flask!
from flask import Flask, render_template, request, send_file, redirect, url_for 
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader

app = Flask(__name__)

def limpiar_nombre_archivo(texto):
    # Limpiamos los saltos de línea para el nombre de archivo
    texto_limpio = texto.replace('\n', ' ').replace('\r', '')
    texto_limpio = texto_limpio.replace(' ', '_')
    texto_limpio = re.sub(r'[^\w-]', '', texto_limpio)
    return texto_limpio[:50]

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
        # La búsqueda ahora también ignora los guiones bajos
        carteles_filtrados = [c for c in lista_completa if query in c.upper().replace('_', ' ')]
    else:
        carteles_filtrados = lista_completa
    return render_template('galeria.html', carteles=carteles_filtrados, search_query=query)

# (El resto de tu app.py, como las importaciones y las otras rutas, no cambia)

@app.route('/generar', methods=['POST'])
def generar_imagen():
    # --- ¡AQUÍ ESTÁ LA CORRECCIÓN! ---
    # Limpiamos los saltos de línea de Windows antes de procesar.
    texto_usuario = request.form['texto'].upper().replace('\r', '')

    try:
        ruta_plantilla = 'static/plantilla.png'
        imagen = Image.open(ruta_plantilla)
        ancho_img, alto_img = imagen.size
        dibujo = ImageDraw.Draw(imagen)
        
        # Usamos la fuente que hayas elegido
        ruta_fuente = 'static/ARIBLK.TTF' # <-- ¡ASEGÚRATE DE QUE ESTE NOMBRE SEA CORRECTO!
        tamaño_fuente = 250
        fuente = ImageFont.truetype(ruta_fuente, tamaño_fuente)
        
        texto_final_multilinea = texto_usuario
        
        caja_texto = dibujo.multiline_textbbox((0, 0), texto_final_multilinea, font=fuente, align="center", spacing=30)
        alto_total_texto = caja_texto[3] - caja_texto[1]
        
        pos_y_inicial = (alto_img - alto_total_texto) / 2
        
        dibujo.multiline_text(
            (ancho_img / 2, pos_y_inicial), 
            texto_final_multilinea, 
            font=fuente, 
            fill="black", 
            anchor="ma",
            align="center",
            spacing=30
        )
        
        # (El resto del código para guardar y crear el PDF no cambia)
        nombre_base = limpiar_nombre_archivo(texto_usuario)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        nombre_archivo = f"{nombre_base}@{timestamp}.png"
        ruta_guardado = os.path.join('static', 'generados', nombre_archivo)
        
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

    except Exception as e:
        return f"Ha ocurrido un error inesperado: {str(e)}", 500

# (El resto del código como la ruta de descarga, eliminar, etc., no cambia)

# --- NUEVA RUTA: Para descargar las imágenes desde la galería ---
@app.route('/descargar/<path:filename>')
def descargar(filename):
    ruta_galeria = os.path.join('static', 'generados')
    return send_file(os.path.join(ruta_galeria, filename), as_attachment=True)

# --- NUEVA RUTA: Para eliminar imágenes de forma segura ---
@app.route('/eliminar', methods=['POST'])
def eliminar():
    filename = request.form.get('filename')
    if filename:
        ruta_archivo = os.path.join('static', 'generados', filename)
        # Doble chequeo de seguridad: nos aseguramos de no salir de la carpeta 'generados'
        if os.path.exists(ruta_archivo) and os.path.dirname(os.path.abspath(ruta_archivo)).endswith('generados'):
            os.remove(ruta_archivo)
    # Redirigimos al usuario de vuelta a la galería
    return redirect(url_for('galeria'))

if __name__ == '__main__':
    app.run(debug=True)