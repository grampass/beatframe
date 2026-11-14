"""Archivos atómicos y bloqueos de trabajo. Sin dependencias de Manim."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def firma(datos):
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha256(ruta):
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def escribir_json(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nombre = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ruta.parent,
                                         prefix=ruta.name + ".", suffix=".tmp", delete=False) as f:
            nombre = f.name
            json.dump(datos, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(nombre, ruta)
    finally:
        if nombre:
            Path(nombre).unlink(missing_ok=True)


def leer_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return defecto


class Bloqueo:
    """Bloqueo del SO: se libera incluso si muere el proceso. El archivo vacío puede permanecer."""
    def __init__(self, ruta):
        self.ruta, self.f = Path(ruta), None

    def __enter__(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.ruta.open("a+b")
        if not self.ruta.stat().st_size:
            self.f.write(b"0")
            self.f.flush()
        self.f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            self.f.close()
            self.f = None
            raise RuntimeError(f"Ya hay otra ejecución usando {self.ruta.parent}") from e
        return self

    def __exit__(self, *exc):
        if self.f:
            self.f.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
            self.f.close()


class CacheEtapas:
    def __init__(self, ruta, automatico=True):
        self.ruta = Path(ruta)
        self.automatico = automatico
        self.datos = leer_json(ruta, {})
        if (not isinstance(self.datos, dict) or self.datos.get("version") != 1
                or not isinstance(self.datos.get("etapas"), dict)):
            self.datos = {"version": 1, "etapas": {}}

    def vigente(self, etapa, clave):
        e = self.datos.get("etapas", {}).get(etapa, {})
        if not isinstance(e, dict) or e.get("firma") != clave or not isinstance(e.get("salidas"), dict) or not e["salidas"]:
            return None
        try:
            if all(Path(p).is_file() and sha256(p) == h for p, h in e["salidas"].items()):
                return e
        except OSError:
            pass
        return None

    def guardar(self, etapa, clave, salidas, **meta):
        e = dict(firma=clave, salidas={str(Path(p).resolve()): sha256(p) for p in salidas}, meta=meta)
        self.datos["etapas"][etapa] = e
        if self.automatico:
            self.confirmar()
        return e

    def confirmar(self):
        escribir_json(self.ruta, self.datos)
