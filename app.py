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
    selected_icon_filename = request.form.get('selected_icon')
    
    # --- NUEVOS PARÁMETROS DINÁMICOS ---
    # Usamos .get() con valores por defecto por si el HTML todavía no los manda
    size_str = request.form.get('size', 'A4')
    orientacion_str = request.form.get('orientation', 'landscape')
    tamaño_fuente = int(request.form.get('font_size', 300))

    try:
        # 1. Crear el lienzo dinámico según el tamaño elegido
        ancho_px, alto_px = PAPER_SIZES_PX.get(size_str, PAPER_SIZES_PX['A4'])
        
        # Si eligieron horizontal, invertimos el ancho por el alto
        if orientacion_str == 'landscape':
            ancho_px, alto_px = alto_px, ancho_px 

        imagen = Image.new("RGBA", (ancho_px, alto_px), "white")
        dibujo = ImageDraw.Draw(imagen)

        # 2. Dibujar la identidad corporativa (CEVA) dinámicamente
        # Calculamos una franja azul para abajo (10% del alto de la hoja)
        alto_franja = int(alto_px * 0.10) 
        margen_inferior = alto_franja + 50 # Espacio extra para que el texto no se pegue
        
        # Dibujamos la franja (Azul oscuro institucional)
        dibujo.rectangle(
            [(0, alto_px - alto_franja), (ancho_px, alto_px)],
            fill="#002A54" 
        )

        # Buscar y pegar el logo en la franja
        ruta_logo = 'static/logo.jpg'
        if os.path.exists(ruta_logo):
            logo = Image.open(ruta_logo).convert("RGBA")
            # Redimensionar el logo para que entre perfecto en la franja (80% del alto)
            alto_logo = int(alto_franja * 0.8)
            proporcion = alto_logo / float(logo.size[1])
            ancho_logo = int(float(logo.size[0]) * float(proporcion))
            
            # Usamos LANCZOS para que no se pixele al achicar/agrandar
            try:
                resample_method = Image.Resampling.LANCZOS
            except AttributeError:
                resample_method = Image.LANCZOS # Compatibilidad con versiones viejas de PIL
                
            logo = logo.resize((ancho_logo, alto_logo), resample_method)
            
            # Posición: Abajo a la derecha
            pos_x_logo = ancho_px - ancho_logo - 50
            pos_y_logo = alto_px - alto_franja + int((alto_franja - alto_logo) / 2)
            
            # Crear máscara para logos con transparencia
            mask = logo if logo.mode == 'RGBA' else None
            imagen.paste(logo, (pos_x_logo, pos_y_logo), mask)

        # (Opcional) Icono adicional centrado arriba si usan esa función
        if selected_icon_filename:
            icon_path = os.path.join('static', selected_icon_filename)
            if os.path.exists(icon_path):
                icon_img = Image.open(icon_path).convert("RGBA")
                icon_size = int(ancho_px * 0.15) # 15% del ancho de la hoja
                icon_img = icon_img.resize((icon_size, icon_size), resample_method)
                icon_x = (ancho_px - icon_size) // 2
                icon_y = 150
                imagen.paste(icon_img, (icon_x, icon_y), icon_img)

        # 3. Configurar y dibujar el texto
        ruta_fuente = 'static/ARIBLK.TTF'
        try:
            fuente = ImageFont.truetype(ruta_fuente, tamaño_fuente)
        except IOError:
            # Fallback seguro por si no encuentra la fuente
            fuente = ImageFont.load_default() 

        # Altura disponible para centrar el texto (restando la franja corporativa)
        altura_disponible = alto_px - margen_inferior
        
        caja_texto = dibujo.multiline_textbbox((0, 0), texto_usuario, font=fuente, align="center", spacing=30)
        alto_total_texto = caja_texto[3] - caja_texto[1]
        
        # Centrado vertical matemático
        pos_y_inicial = (altura_disponible - alto_total_texto) / 2
        
        dibujo.multiline_text(
            (ancho_px / 2, pos_y_inicial), 
            texto_usuario, 
            font=fuente, 
            fill="black", 
            anchor="ma",
            align="center",
            spacing=30
        )

        # 4. Guardar imagen y generar PDF final
        nombre_base = limpiar_nombre_archivo(texto_usuario)
        if not nombre_base:
            nombre_base = "cartel_generado"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        nombre_archivo = f"{nombre_base}@{timestamp}.png"
        
        ruta_generados = os.path.join('static', 'generados')
        os.makedirs(ruta_generados, exist_ok=True)
        ruta_guardado = os.path.join(ruta_generados, nombre_archivo)
        imagen.save(ruta_guardado)
        
        imagen_rgb = imagen.convert('RGB')
        img_io = io.BytesIO()
        imagen_rgb.save(img_io, 'JPEG', quality=95)
        img_io.seek(0)
        
        pdf_io = io.BytesIO()
        
        # Configurar tamaño de página exacto en ReportLab
        rl_size = PAPER_SIZES_RL.get(size_str, A4)
        if orientacion_str == 'landscape':
            rl_size = landscape(rl_size)
        else:
            rl_size = portrait(rl_size)

        c = canvas.Canvas(pdf_io, pagesize=rl_size)
        ancho_pdf, alto_pdf = rl_size
        
        c.drawImage(ImageReader(img_io), 0, 0, width=ancho_pdf, height=alto_pdf, preserveAspectRatio=True, anchor='c')
        c.showPage()
        c.save()
        pdf_io.seek(0)
        
        # Liberar memoria pesada antes de enviar el PDF
        del imagen
        del imagen_rgb
        img_io.close()
        gc.collect() # Fuerza a Python a limpiar la RAM

        forzar_descarga = not accion_imprimir
        return send_file(pdf_io, mimetype='application/pdf', as_attachment=forzar_descarga, download_name=f'cartel_{nombre_base}_{size_str}.pdf')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Ha ocurrido un error inesperado al generar el cartel: {str(e)}", 500

@app.route('/descargar/<path:filename>')
def descargar(filename):
    ruta_galeria = os.path.join('static', 'generados')
    return send_file(os.path.join(ruta_galeria, filename), as_attachment=True)

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
