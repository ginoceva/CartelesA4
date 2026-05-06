import os
import io
import re
from datetime import datetime
from flask import Flask, render_template, request, send_file, redirect, url_for
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, A4, A5, landscape, portrait
from reportlab.lib.utils import ImageReader

app = Flask(__name__)

# Diccionario de tamaños de papel a 300 DPI (Píxeles: Ancho, Alto para orientación Vertical/Portrait)
PAPER_SIZES_PX = {
    'A3': (3508, 4961),
    'A4': (2480, 3508),
    'A5': (1748, 2480)
}

# Diccionario para la librería del PDF (ReportLab)
PAPER_SIZES_RL = {
    'A3': A3,
    'A4': A4,
    'A5': A5
}

def limpiar_nombre_archivo(texto):
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
        carteles_filtrados = [c for c in lista_completa if query in c.upper().replace('_', ' ')]
    else:
        carteles_filtrados = lista_completa
    return render_template('galeria.html', carteles=carteles_filtrados, search_query=query)

@app.route('/generar', methods=['POST'])
def generar_imagen():
    texto_usuario = request.form.get('texto', '').upper().replace('\r', '')
    accion_imprimir = request.form.get('accion') == 'imprimir'
    
    size_str = request.form.get('size', 'A4')
    orientacion_str = request.form.get('orientation', 'landscape')
    tamaño_fuente = int(request.form.get('font_size', 300))
    color_texto_default = request.form.get('text_color', '#000000')
    
    icono_file = request.files.get('icono_file')

    try:
        ancho_px, alto_px = PAPER_SIZES_PX.get(size_str, PAPER_SIZES_PX['A4'])
        if orientacion_str == 'landscape': ancho_px, alto_px = alto_px, ancho_px 

        imagen = Image.new("RGBA", (ancho_px, alto_px), "white")
        dibujo = ImageDraw.Draw(imagen)

        # --- DIBUJAR TRIÁNGULO ROJO ---
        tri_height = int(alto_px * 0.18)
        tri_width = int(ancho_px * 0.04)
        dibujo.polygon([(0, alto_px), (tri_width, alto_px), (0, alto_px - tri_height)], fill="#E3000F")

        # --- PEGAR LOGO FLOTANDO ---
        ruta_logo = 'static/logo.jpg'
        if os.path.exists(ruta_logo):
            logo = Image.open(ruta_logo).convert("RGBA")
            alto_logo = int(alto_px * 0.1)
            proporcion = alto_logo / float(logo.size[1])
            ancho_logo = int(float(logo.size[0]) * float(proporcion))
            try: resample_method = Image.Resampling.LANCZOS
            except AttributeError: resample_method = Image.LANCZOS
            logo = logo.resize((ancho_logo, alto_logo), resample_method)
            
            margin_x = int(ancho_px * 0.04)
            margin_y = int(alto_px * 0.04)
            pos_x = ancho_px - ancho_logo - margin_x
            pos_y = alto_px - alto_logo - margin_y
            
            imagen.paste(logo, (pos_x, pos_y), logo if logo.mode == 'RGBA' else None)

        top_offset = 0
        if icono_file and icono_file.filename != '':
            try:
                simbolo_img = Image.open(icono_file.stream).convert("RGBA")
                icon_size = int(alto_px * 0.20) 
                simbolo_img = simbolo_img.resize((icon_size, icon_size), resample_method)
                icon_x = (ancho_px - icon_size) // 2
                icon_y = int(alto_px * 0.05)
                imagen.paste(simbolo_img, (icon_x, icon_y), simbolo_img)
                top_offset = icon_y + icon_size + 50 
            except Exception as e:
                print(f"Error procesando icono: {e}")

        try:
            fuente_normal = ImageFont.truetype('static/arialbd.ttf', tamaño_fuente)
            fuente_negrita = ImageFont.truetype('static/ARIBLK.TTF', tamaño_fuente)
        except IOError:
            fuente_normal = ImageFont.load_default()
            fuente_negrita = ImageFont.load_default()

        margen_inferior = int(alto_px * 0.15)
        altura_disponible = alto_px - margen_inferior - top_offset
        lineas = texto_usuario.split('\n')
        alto_total_texto = (len(lineas) * tamaño_fuente) + ((len(lineas) - 1) * 30)
        pos_y_inicial = top_offset + (altura_disponible - alto_total_texto) / 2
        
        patron_tags = r'(\[B\]|\[/B\]|\[U\]|\[/U\]|\[C=#[0-9A-F]{6}\]|\[/C\])'

        for i, linea in enumerate(lineas):
            partes = re.split(patron_tags, linea)
            
            es_negrita = False
            es_subrayado = False
            pila_colores = [color_texto_default]
            tokens = []

            for parte in partes:
                if not parte: continue
                if parte == '[B]': es_negrita = True
                elif parte == '[/B]': es_negrita = False
                elif parte == '[U]': es_subrayado = True
                elif parte == '[/U]': es_subrayado = False
                elif parte.startswith('[C='): pila_colores.append(parte[3:10])
                elif parte == '[/C]': 
                    if len(pila_colores) > 1: pila_colores.pop()
                else:
                    tokens.append({
                        'texto': parte, 
                        'negrita': es_negrita, 
                        'subrayado': es_subrayado, 
                        'color': pila_colores[-1]
                    })

            ancho_linea = 0
            for t in tokens:
                f_actual = fuente_negrita if t['negrita'] else fuente_normal
                ancho_linea += dibujo.textlength(t['texto'], font=f_actual)

            x_actual = (ancho_px - ancho_linea) / 2
            y_actual = pos_y_inicial + (i * (tamaño_fuente + 30))

            for t in tokens:
                f_actual = fuente_negrita if t['negrita'] else fuente_normal
                ancho_pedazo = dibujo.textlength(t['texto'], font=f_actual)
                
                dibujo.text((x_actual, y_actual), t['texto'], font=f_actual, fill=t['color'], anchor="la")
                
                if t['subrayado'] and t['texto'].strip():
                    y_subrayado = y_actual + tamaño_fuente * 1.05
                    grosor = max(int(tamaño_fuente * 0.05), 3)
                    dibujo.line([(x_actual, y_subrayado), (x_actual + ancho_pedazo, y_subrayado)], fill=t['color'], width=grosor)
                
                x_actual += ancho_pedazo

        texto_limpio_sin_tags = re.sub(patron_tags, '', texto_usuario)
        nombre_base = limpiar_nombre_archivo(texto_limpio_sin_tags) or "cartel_generado"
        nombre_archivo = f"{nombre_base}@{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        ruta_generados = os.path.join('static', 'generados')
        os.makedirs(ruta_generados, exist_ok=True)
        imagen.save(os.path.join(ruta_generados, nombre_archivo))
        
        imagen_rgb = imagen.convert('RGB')
        img_io = io.BytesIO()
        imagen_rgb.save(img_io, 'JPEG', quality=95)
        img_io.seek(0)
        
        pdf_io = io.BytesIO()
        rl_size = PAPER_SIZES_RL.get(size_str, PAPER_SIZES_RL['A4'])
        rl_size = landscape(rl_size) if orientacion_str == 'landscape' else portrait(rl_size)

        c = canvas.Canvas(pdf_io, pagesize=rl_size)
        c.drawImage(ImageReader(img_io), 0, 0, width=rl_size[0], height=rl_size[1], preserveAspectRatio=True, anchor='c')
        c.showPage()
        c.save()
        pdf_io.seek(0)
        
        del imagen
        del imagen_rgb
        img_io.close()
        import gc
        gc.collect()

        return send_file(pdf_io, mimetype='application/pdf', as_attachment=not accion_imprimir, download_name=f'cartel_{nombre_base}_{size_str}.pdf')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Ha ocurrido un error inesperado: {str(e)}", 500

@app.route('/eliminar', methods=['POST'])
def eliminar():
    filename = request.form.get('filename')
    if filename:
        ruta_archivo = os.path.join('static', 'generados', filename)
        if os.path.exists(ruta_archivo) and os.path.dirname(os.path.abspath(ruta_archivo)).endswith('generados'):
            os.remove(ruta_archivo)
    return redirect(url_for('galeria'))

if __name__ == '__main__':
    app.run(debug=True)
