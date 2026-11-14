"""Avisos orientativos sobre fotogramas reales, incluidos fondos PNG. No certifica WCAG.

Se estima el fondo en la caja del texto descartando su color; se tiene en cuenta el contorno.
Referencia del umbral 4,5: https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum
"""
import numpy as np


def luminancia(rgb):
    x = np.asarray(rgb, dtype=float) / 255
    x = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    return x @ np.array([0.2126, 0.7152, 0.0722])


def razon(a, b):
    la, lb = float(luminancia(a)), float(luminancia(b))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def estimar(imagen, texto, umbral=4.5):
    w, h = imagen.size
    x0, y0, x1, y1 = texto["caja"]
    a, b = max(0, int((x0+4.5)/9*w)), min(w, int(np.ceil((x1+4.5)/9*w)))
    c, d = max(0, int((8-y1)/16*h)), min(h, int(np.ceil((8-y0)/16*h)))
    if a >= b or c >= d or "color" not in texto:
        return None
    pix = np.asarray(imagen.convert("RGB"))[c:d, a:b].reshape(-1, 3).astype(float)
    color = np.asarray(texto["color"], float)
    diferentes = pix[np.linalg.norm(pix-color, axis=1) > 45]
    fondo = np.median(diferentes if len(diferentes) > len(pix)*0.15 else pix, axis=0)
    r = razon(color, fondo)
    if texto.get("contorno_ancho", 0) >= 2 and texto.get("contorno_opacidad", 0) >= 0.8:
        r = max(r, razon(color, texto["contorno_color"]))
    if r >= umbral:
        return None
    return dict(tipo="contraste_estimado", texto=texto["nombre"], caja=texto["caja"],
                razon=round(r, 2), umbral=umbral,
                nota="Estimación de color/fondo local; comprobar la captura, no es certificación de accesibilidad.")
