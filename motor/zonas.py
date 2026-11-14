"""Perfiles de revisión normalizados. Las estimaciones orgánicas NO son datos oficiales.

Rectángulos [izquierda, arriba, derecha, abajo] en fracciones del lienzo 9:16.
No alteran escenas antiguas. Una máscara es una ayuda de revisión, no una garantía por dispositivo.
"""
from copy import deepcopy

TIKTOK = "https://ads.tiktok.com/resources/help/article/tiktok-auction-in-feed-ads?lang=en"
YOUTUBE = "https://support.google.com/youtube/answer/16215842?hl=es"
META = "https://www.facebook.com/business/help/980593475366490"
FECHA = "2026-11-12"
PERFILES = {
    "legado": dict(nombre="Margen común anterior", rectangulos=[[0, 0, 0.85, 0.8]],
                   evidencia="estimacion_proyecto", alcance="compatibilidad", fuente="motor/nucleo.py: Y_MIN y X_MAX"),
    "youtube": dict(nombre="YouTube Shorts · estimación", rectangulos=[[0.06, 0.14, 0.82, 0.76]],
                    evidencia="estimacion_proyecto", alcance="organico", fuente=YOUTUBE,
                    nota="YouTube explica guías visuales, no estas cifras. Validar en la app/dispositivo."),
    "tiktok": dict(nombre="TikTok orgánico · estimación", rectangulos=[[0.1112, 0.125, 0.7222, 0.65625]],
                   evidencia="estimacion_proyecto", alcance="organico", fuente=TIKTOK,
                   nota="Margen conservador inspirado en la plantilla publicitaria. No es una especificación orgánica."),
    "instagram": dict(nombre="Instagram Reels · estimación", rectangulos=[[0.06, 0.14, 0.88, 0.70]],
                      evidencia="estimacion_proyecto", alcance="organico", fuente=META,
                      nota="Cifras del proyecto; la fuente Meta requirió inicio de sesión. Pendiente validación en la app."),
    "facebook": dict(nombre="Facebook Reels · estimación", rectangulos=[[0.06, 0.14, 0.88, 0.70]],
                     evidencia="estimacion_proyecto", alcance="organico", fuente=META,
                     nota="Cifras del proyecto; no se atribuyen a Meta. Pendiente validación en la app."),
    "tiktok-anuncio": dict(nombre="TikTok In-Feed estándar LTR · plantilla oficial",
                           rectangulos=[[80/720, 160/1280, 640/720, 560/1280],
                                        [80/720, 560/1280, 520/720, 840/1280]],
                           evidencia="medida_plantilla_oficial", alcance="anuncio_infeed_sin_anchor", fuente=TIKTOK,
                           archivo="https://lf-tt4b.tiktokcdn.com/obj/i18nblog/tt4b_cms/en-US/5jqet0ab9qci-10e7f5Vig4uhAscNP8XPB0.zip",
                           nota="Feed.png 2880×5120, medidas rotuladas a 720×1280. No cubre otras descripciones/anchors/dispositivos."),
}


def perfil(nombre="legado"):
    if nombre not in PERFILES:
        raise ValueError(f"Perfil desconocido: {nombre}. Opciones: {', '.join(PERFILES)}")
    return dict(deepcopy(PERFILES[nombre]), id=nombre, consultado=FECHA)


def normalizar(caja, ancho=9, alto=16):
    x0, y0, x1, y1 = caja
    return [x0 / ancho + 0.5, 0.5 - y1 / alto, x1 / ancho + 0.5, 0.5 - y0 / alto]


def contiene(caja, nombre="legado", tolerancia=0.0):
    """Cobertura por la UNIÓN de rectángulos, incluidas cajas que cruzan el escalón de TikTok."""
    x0, y0, x1, y1 = caja
    rs = perfil(nombre)["rectangulos"]
    xs = sorted({x0, x1, *(max(x0, min(x1, r[k])) for r in rs for k in (0, 2))})
    ys = sorted({y0, y1, *(max(y0, min(y1, r[k])) for r in rs for k in (1, 3))})
    if x1 <= x0 or y1 <= y0:
        return False
    for a, b in zip(xs, xs[1:]):
        for c, d in zip(ys, ys[1:]):
            if b <= a or d <= c:
                continue
            x, y = (a+b)/2, (c+d)/2
            if not any(r[0]-tolerancia <= x <= r[2]+tolerancia and r[1]-tolerancia <= y <= r[3]+tolerancia for r in rs):
                return False
    return True


def caja_conservadora(nombre="legado"):
    """Rectángulo seguro común a toda la altura del perfil (coordenadas de Manim)."""
    rs = perfil(nombre)["rectangulos"]
    return (max(r[0] for r in rs)*9-4.5, min(r[2] for r in rs)*9-4.5,
            8-max(r[3] for r in rs)*16, 8-min(r[1] for r in rs)*16)


def superponer(imagen, nombre):
    from PIL import Image, ImageDraw
    p = perfil(nombre)
    w, h = imagen.size
    capa = Image.new("RGBA", (w, h), (255, 40, 80, 95))
    d = ImageDraw.Draw(capa)
    for x0, y0, x1, y1 in p["rectangulos"]:
        d.rectangle((round(x0*w), round(y0*h), round(x1*w), round(y1*h)), fill=(0, 0, 0, 0), outline=(100, 255, 160, 220), width=2)
    out = Image.alpha_composite(imagen.convert("RGBA"), capa).convert("RGB")
    d = ImageDraw.Draw(out)
    d.rectangle((0, 0, w, 36), fill="#16181F")
    d.text((6, 4), p["nombre"], fill="white")
    d.text((6, 19), f"{p['evidencia']} / {FECHA}", fill="#FFB547")
    return out
