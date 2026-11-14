"""Dependencias, caché por etapas y traspaso breve de producción."""
import importlib.metadata
import json
import os
import platform
import re
import time
from pathlib import Path

from artefactos import escribir_json, firma, leer_json, sha256
from configuracion import archivos_configuracion, ruta as ruta_config

MOTOR = Path(__file__).resolve().parent
RAIZ = MOTOR.parent


def cerrado(carpeta):
    p = Path(carpeta) / "README.md"
    if not p.exists():
        return False
    m = re.search(r"\*\*Rol:\*\*\s*(.+)", p.read_text(encoding="utf-8"))
    return bool(m and m[1].strip().lower().startswith("publicado"))


def dependencias(carpeta):
    """Firma conservadora: fuentes del motor, recursos y entradas locales; nunca outputs de una ejecución."""
    carpeta = Path(carpeta).resolve()
    g = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
    archivos = set()
    archivos.update(p for p in MOTOR.rglob("*.py") if "_archivo" not in p.parts and
                    not p.name.startswith("pruebas_") and p.name not in ("regresion.py", "inventario.py", "papelera.py"))
    archivos.update(archivos_configuracion())
    archivos.update(p for p in ruta_config("assets", MOTOR / "recursos").rglob("*") if p.is_file())
    extensiones = {".py", ".png", ".jpg", ".jpeg", ".svg", ".wav", ".mp3", ".ttf", ".otf", ".cfg"}
    for p in carpeta.rglob("*"):
        partes = p.relative_to(carpeta).parts
        if any(x in ("render", "revision", "_archivo", "__pycache__") for x in partes):
            continue
        if p.is_file() and p.suffix.lower() in extensiones:
            archivos.add(p)
    for ruta in g.get("dependencias", []):
        p = Path(ruta)
        p = p if p.is_absolute() else carpeta / p
        if not p.is_file():
            raise ValueError(f"Dependencia declarada inexistente: {ruta}")
        archivos.add(p.resolve())
    for p in (RAIZ / "manim.cfg", carpeta / "manim.cfg"):
        if p.is_file():
            archivos.add(p)
    # Tiempos forman parte de la imagen: subtítulos y boca dependen de ellos.
    if (carpeta / "audio" / "tiempos.json").is_file():
        archivos.add(carpeta / "audio" / "tiempos.json")
    versiones = {}
    for nombre in ("manim", "numpy", "Pillow", "manimpango", "edge-tts"):
        try:
            versiones[nombre] = importlib.metadata.version(nombre)
        except importlib.metadata.PackageNotFoundError:
            versiones[nombre] = "no instalado"
    fuentes = []
    for d in (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
              Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts"):
        if d.is_dir():
            fuentes += [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(d.iterdir()) if p.is_file()]
    entorno = {k: os.environ.get(k, "") for k in ("PLANO_VER", "PANGOCAIRO_BACKEND", "FONTCONFIG_FILE", "FONTCONFIG_PATH")}
    # Huella del ejecutable externo: una actualización invalida la salida, sin ejecutar servicios de red.
    import shutil
    herramientas = {n: sha256(shutil.which(n)) if shutil.which(n) else None for n in ("ffmpeg", "ffprobe")}
    return dict(guion=g, archivos={str(p): sha256(p) for p in sorted(archivos)}, versiones=versiones,
                fuentes=fuentes, entorno=entorno, herramientas=herramientas, plataforma=platform.platform())


def plan_firma(carpeta):
    p = Path(carpeta) / "sonido.json"
    return sha256(p) if p.is_file() else None


def sin_ganancias(eventos):
    return {k: [{a: v for a, v in e.items() if a != "db"} for e in eventos.get(k, [])]
            for k in ("ambientes", "efectos", "pistas")}


def eventos_reutilizados(anterior_previo, anterior_real, nuevo_previo):
    """Solo cambia ganancias: mantiene las marcas del render real, no las aproxima con el dry-run."""
    if sin_ganancias(anterior_previo) != sin_ganancias(nuevo_previo):
        return None
    datos = json.loads(json.dumps(anterior_real))
    for tipo in ("ambientes", "efectos", "pistas"):
        reales, nuevos = datos.get(tipo, []), nuevo_previo.get(tipo, [])
        if len(reales) != len(nuevos):
            return None
        for a, b in zip(reales, nuevos):
            if any(a.get(k) != b.get(k) for k in ("nombre", "archivo", "clave")):
                return None
            a["db"] = b["db"]
    return datos


def vigencia_visual(carpeta, firma_imagen):
    p = Path(carpeta) / "revision" / "revision-visual.md"
    if not p.is_file():
        return "pendiente"
    s = p.read_text(encoding="utf-8")
    m = re.search(r"Firma-imagen:\s*([a-f0-9]{64})", s)
    reviso = re.search(r"^- Revisó:[ \t]*([^\r\n]+)", s, re.M)
    if not m or m[1] != firma_imagen:
        return "desactualizada"
    return "declarada vigente por autor" if reviso and "- [ ]" not in s and "- [x]" in s.lower() else "pendiente"


def preparar_revision(carpeta, firma_imagen):
    out = Path(carpeta) / "revision"
    visual = out / "revision-visual.md"
    if not visual.exists():
        visual.write_text(f"# Revisión visual\n\nFirma-imagen: {firma_imagen}\n\n- Fecha y versión revisada:\n- Revisó:\n\n"
                          "- [ ] Texto, imagen y actuación corresponden al guion\n"
                          "- [ ] Miré contacto y hojas finales, con sus avisos\n"
                          "- [ ] Sin superposiciones ni elementos importantes tapados\n"
                          "- [ ] Revisé transiciones y audio en el video cuando correspondía\n\n"
                          "Una hoja no acredita escucha integral. Control C y permiso de publicar los da el usuario.\n",
                          encoding="utf-8")
    estado = vigencia_visual(carpeta, firma_imagen)
    escribir_json(out / "revision-vigencia.json", dict(firma_imagen=firma_imagen, visual=estado,
                  ciencia="Consultar dictamen y alcance del autor; no certificado automáticamente",
                  control_usuario="No inferido por el motor"))
    return estado


class Informe:
    def __init__(self, carpeta, modo, ejecucion):
        self.carpeta, self.modo, self.ejecucion = Path(carpeta), modo, ejecucion
        self.inicio, self.pasos, self.avisos = time.monotonic(), [], []
        self.marca = self.inicio
        self.datos = {}

    def paso(self, codigo, ok, detalle="", reutilizado=False):
        ahora = time.monotonic()
        self.pasos.append(dict(codigo=codigo, estado="reutilizado" if ok and reutilizado else "ok" if ok else "error",
                               detalle=str(detalle), segundos=round(ahora - self.marca, 3)))
        self.marca = ahora
        print(f"[{'CACHE' if reutilizado else 'OK' if ok else 'ERROR'}] {codigo}" + (f": {detalle}" if detalle else ""))
        return ok

    def aviso(self, codigo, mensaje):
        self.avisos.append(dict(codigo=codigo, mensaje=str(mensaje), nivel="aviso"))

    def terminar(self):
        ok = all(p["estado"] != "error" for p in self.pasos)
        previo = leer_json(self.carpeta / "revision" / "resumen.json", {}) or {}
        actual = dict(version=1, estado="ok" if ok else "error", modo=self.modo, ejecucion=self.ejecucion,
                      segundos=round(time.monotonic() - self.inicio, 3), etapas=self.pasos, avisos=self.avisos, **self.datos)
        antes = {p["codigo"]: p for p in previo.get("etapas", [])}
        comparable = lambda p: {k: v for k, v in p.items() if k != "segundos"}
        actual["cambios"] = [p["codigo"] for p in self.pasos if comparable(p) != comparable(antes.get(p["codigo"], {}))]
        # El intento actual siempre queda explícito; un final antiguo nunca se presenta como resultado de un fallo.
        actual["entrega_actual"] = self.datos.get("entrega") if ok else None
        out = self.carpeta / "revision"
        escribir_json(out / "resumen.json", actual)
        escribir_json(out / "ejecuciones" / self.ejecucion / "resumen.json", actual)
        errores = [p for p in self.pasos if p["estado"] == "error"]
        breve = [f"# Producción · {self.modo}", "", f"Estado: {'SUPERADAS' if ok else 'CON ERRORES'} · {actual['segundos']:.1f} s",
                 f"Ejecución: {self.ejecucion}", f"Etapas reutilizadas: {sum(p['estado']=='reutilizado' for p in self.pasos)}",
                 f"Revisión visual: {self.datos.get('revision_visual', 'pendiente')}",
                 "La ciencia, el control C y el permiso de publicar no se aprueban automáticamente.", ""]
        breve += [f"- {p['codigo']}: {p['detalle']}" for p in errores]
        breve += [f"- Aviso {p['codigo']}: {p['mensaje']}" for p in self.avisos[:6]]
        breve += ["", "Detalle técnico: resumen.json. Material revisado: hojas y archivos indicados en ese registro."]
        (out / "informe.md").write_text("\n".join(breve[:20]) + "\n", encoding="utf-8")
        print(f"Resultado: {actual['estado']} · {out / 'informe.md'}")
        return 0 if ok else 1
