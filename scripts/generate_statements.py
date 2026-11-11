"""Generates realistic statements from fictional banks, with known patterns planted on purpose.

Every profile hides findings the analysis must report: ant expenses, subscriptions, duplicated
charges, unusual fees or outliers. Running with the same seed always gives the same files.

    python scripts/generate_statements.py --out output
"""

import argparse
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

SEED = 2026
MONTHS = ((2026, 8), (2026, 9), (2026, 10))
LONG_HISTORY = ((2026, 6), (2026, 7), *MONTHS)
PAGE_TOP = 720
PAGE_BOTTOM = 60
ROW_HEIGHT = 14


@dataclass(frozen=True)
class Movement:
    day: date
    description: str
    cents: int  # positive is income, negative is expense


@dataclass(frozen=True)
class Profile:
    slug: str
    holder: str
    bank: str
    opening_cents: int
    build: Callable[[random.Random, int, int], list[Movement]]
    months: tuple[tuple[int, int], ...] = MONTHS


def _month_days(year: int, month: int) -> list[date]:
    first = date(year, month, 1)
    following = date(year + month // 12, month % 12 + 1, 1)
    return [first + timedelta(days=n) for n in range((following - first).days)]


def _pesos(value: int) -> int:
    return value * 100


def student(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[0], "TRANSFERENCIA MESADA FAMILIA", _pesos(1_200_000)),
        Movement(days[4], "SPOTIFY PREMIUM", -_pesos(16_900)),
        Movement(days[9], "PAGO UNIVERSIDAD CUOTA", -_pesos(350_000)),
    ]
    for day in rng.sample(days, 11):
        moves.append(Movement(day, "CAFE JUAN VALDEZ", -_pesos(rng.randint(6_500, 9_500))))
    for day in rng.sample(days, 6):
        moves.append(Movement(day, "UBER TRIP", -_pesos(rng.randint(9_000, 18_000))))
    for day in rng.sample(days, 4):
        moves.append(Movement(day, "RAPPI RESTAURANTE", -_pesos(rng.randint(25_000, 42_000))))
    if month == 10:
        moves.append(Movement(days[20], "AMAZON COMPRA CONSOLA", -_pesos(1_850_000)))
    return moves


def freelancer(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[2], "AWS CLOUD SERVICES", -_pesos(rng.randint(92_000, 98_000))),
        Movement(days[2], "GITHUB SUBSCRIPTION", -_pesos(19_000)),
        Movement(days[14], "NETFLIX COM", -_pesos(44_900)),
        Movement(days[5], "COWORKING ESPACIO", -_pesos(280_000)),
    ]
    for _ in range(rng.randint(2, 4)):
        amount = _pesos(rng.randrange(800_000, 3_500_000, 50_000))
        moves.append(Movement(rng.choice(days), "PAGO CLIENTE PROYECTO", amount))
    for day in rng.sample(days, 5):
        moves.append(Movement(day, "DIDI VIAJE", -_pesos(rng.randint(8_000, 22_000))))
    if month == 10:
        moves.append(Movement(days[15], "NETFLIX COM", -_pesos(44_900)))
    return moves


def small_business(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[14], "PAGO NOMINA EMPLEADOS", -_pesos(6_400_000)),
        Movement(days[4], "ARRIENDO LOCAL COMERCIAL", -_pesos(2_100_000)),
        Movement(days[7], "ENERGIA ELECTRICA EMPRESA", -_pesos(rng.randint(380_000, 450_000))),
        Movement(days[11], "CLARO INTERNET EMPRESAS", -_pesos(189_900)),
    ]
    for day in rng.sample(days, 12):
        moves.append(Movement(day, "VENTAS DATAFONO", _pesos(rng.randint(450_000, 1_300_000))))
    for day in rng.sample(days, 4):
        moves.append(
            Movement(day, "PROVEEDOR DISTRIBUIDORA", -_pesos(rng.randint(600_000, 1_400_000)))
        )
    if month == 10:
        moves.append(Movement(days[22], "COMISION SOBREGIRO", -_pesos(87_500)))
    return moves


def family(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[0], "NOMINA EMPRESA SAS", _pesos(4_800_000)),
        Movement(days[14], "NOMINA EMPRESA SAS", _pesos(4_800_000)),
        Movement(days[2], "PAGO ARRIENDO APARTAMENTO", -_pesos(2_300_000)),
        Movement(days[8], "ACUEDUCTO ALCANTARILLADO", -_pesos(rng.randint(95_000, 120_000))),
        Movement(days[9], "ENERGIA HOGAR", -_pesos(rng.randint(140_000, 190_000))),
        Movement(days[10], "MOVISTAR HOGAR", -_pesos(129_900)),
        Movement(days[5], "COLEGIO PENSION", -_pesos(780_000)),
        Movement(days[19], "DISNEY PLUS", -_pesos(38_900)),
    ]
    for week in range(4):
        moves.append(
            Movement(days[week * 7 + 1], "MERCADO EXITO", -_pesos(rng.randint(260_000, 420_000)))
        )
    for day in rng.sample(days, 3):
        moves.append(Movement(day, "DROGUERIA FARMACIA", -_pesos(rng.randint(18_000, 65_000))))
    return moves


def driver(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[4], "CUOTA CREDITO VEHICULO", -_pesos(1_150_000)),
        Movement(days[9], "SOAT SEGURO VEHICULO", -_pesos(58_000)),
        Movement(days[11], "TIGO PLAN DATOS", -_pesos(55_000)),
    ]
    for day in days[::2]:
        earnings = _pesos(rng.randint(140_000, 260_000))
        moves.append(Movement(day, "PAGO UBER DRIVER", earnings))
    for day in rng.sample(days, 9):
        moves.append(Movement(day, "GASOLINA TERPEL", -_pesos(rng.randint(70_000, 110_000))))
    for day in rng.sample(days, 7):
        moves.append(Movement(day, "PEAJE AUTOPISTA", -_pesos(rng.choice((11_200, 13_400)))))
    for day in rng.sample(days, 8):
        moves.append(Movement(day, "TIENDA BARRIO EMPANADAS", -_pesos(rng.randint(4_500, 8_500))))
    if month == 10:
        moves.append(Movement(days[17], "TALLER MECANICO MOTOR", -_pesos(2_400_000)))
    return moves


def teacher(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[14], "NOMINA SECRETARIA EDUCACION", _pesos(3_900_000)),
        Movement(days[1], "SMARTFIT MEMBRESIA", -_pesos(79_900)),
        Movement(days[3], "PAGO ARRIENDO APARTAESTUDIO", -_pesos(1_250_000)),
        Movement(days[12], "CLARO HOGAR", -_pesos(99_900)),
        Movement(days[18], "COURSERA PLUS", -_pesos(58_000)),
    ]
    for day in rng.sample(days, 9):
        moves.append(Movement(day, "PANADERIA EL TRIGAL", -_pesos(rng.randint(5_000, 9_000))))
    for day in rng.sample(days, 3):
        moves.append(Movement(day, "LIBRERIA NACIONAL", -_pesos(rng.randint(35_000, 90_000))))
    for week in range(4):
        amount = -_pesos(rng.randint(90_000, 160_000))
        moves.append(Movement(days[week * 7 + 5], "MERCADO D1", amount))
    if month == 10:
        moves.append(Movement(days[2], "SMARTFIT MEMBRESIA", -_pesos(79_900)))
    return moves


def doctor(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    private_practice = _pesos(rng.randint(2_000_000, 3_800_000))
    moves = [
        Movement(days[0], "HONORARIOS CLINICA CENTRAL", _pesos(11_500_000)),
        Movement(days[15], "HONORARIOS CONSULTA PRIVADA", private_practice),
        Movement(days[5], "CUOTA HIPOTECA APARTAMENTO", -_pesos(3_600_000)),
        Movement(days[7], "MEDISALUD POLIZA", -_pesos(420_000)),
        Movement(days[8], "NETFLIX COM", -_pesos(44_900)),
        Movement(days[8], "SPOTIFY FAMILIAR", -_pesos(26_900)),
    ]
    for day in rng.sample(days, 6):
        moves.append(Movement(day, "RESTAURANTE ANDRES", -_pesos(rng.randint(120_000, 260_000))))
    for day in rng.sample(days, 10):
        moves.append(Movement(day, "CAFE JUAN VALDEZ", -_pesos(rng.randint(9_000, 15_000))))
    for day in rng.sample(days, 2):
        moves.append(Movement(day, "FALABELLA COMPRAS", -_pesos(rng.randint(250_000, 600_000))))
    if month == 10:
        moves.append(Movement(days[21], "AVIANCA TIQUETES INTERNACIONALES", -_pesos(7_800_000)))
    return moves


def online_shop(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[1], "SHOPIFY PLAN TIENDA", -_pesos(140_000)),
        Movement(days[2], "META ADS PUBLICIDAD", -_pesos(rng.randint(450_000, 520_000))),
        Movement(days[6], "SERVIENTREGA ENVIOS", -_pesos(rng.randint(300_000, 420_000))),
        Movement(days[20], "SERVIENTREGA ENVIOS", -_pesos(rng.randint(300_000, 420_000))),
    ]
    for day in rng.sample(days, 14):
        moves.append(Movement(day, "VENTAS WOMPI TIENDA", _pesos(rng.randint(180_000, 650_000))))
    for day in rng.sample(days, 3):
        moves.append(Movement(day, "PROVEEDOR TEXTILES", -_pesos(rng.randint(900_000, 1_600_000))))
    for day in rng.sample(days, 6):
        moves.append(Movement(day, "RAPPI RESTAURANTE", -_pesos(rng.randint(22_000, 38_000))))
    if month == 10:
        moves.append(Movement(days[24], "COMISION TRANSFERENCIA INTERNACIONAL", -_pesos(64_000)))
    return moves


def designer(rng: random.Random, year: int, month: int) -> list[Movement]:
    days = _month_days(year, month)
    moves = [
        Movement(days[3], "ADOBE CREATIVE CLOUD", -_pesos(239_000)),
        Movement(days[3], "FIGMA PROFESIONAL", -_pesos(64_000)),
        Movement(days[6], "PAGO ARRIENDO ESTUDIO", -_pesos(1_450_000)),
        Movement(days[10], "ENERGIA HOGAR", -_pesos(rng.randint(110_000, 150_000))),
    ]
    for _ in range(rng.randint(3, 5)):
        amount = _pesos(rng.randrange(900_000, 2_800_000, 50_000))
        moves.append(Movement(rng.choice(days), "PAGO CLIENTE DISENO", amount))
    for day in rng.sample(days, 9):
        moves.append(Movement(day, "CAFE TOSTAO", -_pesos(rng.randint(4_500, 7_500))))
    for day in rng.sample(days, 5):
        moves.append(Movement(day, "RAPPI RESTAURANTE", -_pesos(rng.randint(24_000, 39_000))))
    if month == 10:
        moves.append(Movement(days[4], "ADOBE CREATIVE CLOUD", -_pesos(239_000)))
        moves.append(Movement(days[19], "MACBOOK PRO TIENDA APPLE", -_pesos(9_900_000)))
    return moves


def heavy(rng: random.Random, year: int, month: int) -> list[Movement]:
    """Two thousand movements, so the main thread versus Web Worker difference is visible."""
    days = _month_days(year, month)
    shops = ["TIENDA BARRIO", "PANADERIA", "UBER TRIP", "RAPPI", "MERCADO EXITO", "CAFE"]
    moves = [Movement(days[0], "VENTAS CONSOLIDADAS", _pesos(90_000_000))]
    for _ in range(2000):
        amount = -_pesos(rng.randint(3_000, 60_000))
        moves.append(Movement(rng.choice(days), rng.choice(shops), amount))
    return moves


PROFILES = (
    Profile("estudiante", "VALENTINA ROJAS", "andino", _pesos(450_000), student),
    Profile("freelancer", "ANDRES GOMEZ", "sur", _pesos(3_200_000), freelancer),
    Profile("pyme", "PANADERIA LA ESPIGA SAS", "andino", _pesos(12_500_000), small_business),
    Profile("familia", "CAROLINA MEJIA", "sur", _pesos(2_100_000), family),
    Profile("conductor", "JHON FREDY MUNOZ", "andino", _pesos(900_000), driver, LONG_HISTORY),
    Profile("docente", "LAURA CASTILLO", "sur", _pesos(1_400_000), teacher, LONG_HISTORY),
    Profile("medica", "SOFIA ARANGO", "andino", _pesos(8_000_000), doctor, LONG_HISTORY),
    Profile("emprendedora", "MARIANA TORRES", "sur", _pesos(2_600_000), online_shop, LONG_HISTORY),
    Profile("disenadora", "ISABELA RUIZ", "sur", _pesos(1_900_000), designer),
)


def _colombian(cents: int) -> str:
    text = f"{abs(cents) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{text}" if cents < 0 else text


def _american(cents: int) -> str:
    return f"{abs(cents) / 100:,.2f}"


class StatementWriter:
    def __init__(self, path: Path, header: list[str], columns: str) -> None:
        # invariant=1 leaves out timestamps, so the same data always yields the same bytes.
        self._canvas = Canvas(str(path), pagesize=letter, invariant=1)
        self._header = header
        self._columns = columns
        self._page = 1
        self._y = self._start_page()

    def _start_page(self) -> int:
        y = PAGE_TOP
        self._canvas.setFont("Helvetica-Bold", 15)
        self._canvas.drawString(40, y, self._header[0])
        self._canvas.setFont("Helvetica", 9)
        for line in self._header[1:]:
            y -= ROW_HEIGHT
            self._canvas.drawString(40, y, line)
        y -= ROW_HEIGHT * 2
        self._canvas.setFont("Helvetica-Bold", 9)
        self._canvas.drawString(40, y, self._columns)
        self._canvas.setFont("Helvetica", 9)
        return y - ROW_HEIGHT

    def row(self, cells: list[tuple[float, str, str]]) -> None:
        if self._y < PAGE_BOTTOM:
            self._canvas.drawString(40, 30, f"Página {self._page}")
            self._canvas.showPage()
            self._page += 1
            self._y = self._start_page()
        for x, text, align in cells:
            draw = self._canvas.drawRightString if align == "right" else self._canvas.drawString
            draw(x, self._y, text)
        self._y -= ROW_HEIGHT

    def finish(self, footer: str) -> None:
        self.row([(40, footer, "left")])
        self._canvas.drawString(40, 30, f"Página {self._page}")
        self._canvas.save()


def write_andino(path: Path, profile: Profile, moves: list[Movement], opening: int) -> int:
    first, last = moves[0].day.replace(day=1), max(m.day for m in moves)
    period_end = _month_days(first.year, first.month)[-1]
    header = [
        "BANCO ANDINO",
        "Extracto de cuenta de ahorros",
        f"Titular: {profile.holder}",
        "Cuenta: ****4821",
        f"Periodo: {first:%d/%m/%Y} - {max(last, period_end):%d/%m/%Y}",
        f"Saldo anterior: $ {_colombian(opening)}",
    ]
    columns = "Fecha        Descripción                       Valor        Saldo"
    writer = StatementWriter(path, header, columns)
    balance = opening
    for move in moves:
        balance += move.cents
        writer.row(
            [
                (40, f"{move.day:%d/%m/%Y}", "left"),
                (110, move.description, "left"),
                (450, _colombian(move.cents), "right"),
                (550, _colombian(balance), "right"),
            ]
        )
    writer.finish(f"Saldo final: $ {_colombian(balance)}")
    return balance


def write_sur(path: Path, profile: Profile, moves: list[Movement], opening: int) -> int:
    first = moves[0].day.replace(day=1)
    period_end = _month_days(first.year, first.month)[-1]
    header = [
        "COOPERATIVA SUR",
        "Estado de cuenta de ahorro cooperativo",
        f"Asociado: {profile.holder}",
        f"Desde {first:%Y-%m-%d} hasta {period_end:%Y-%m-%d}",
        f"Saldo inicial $ {_american(opening)}",
    ]
    columns = "Fecha        Concepto                              Tipo       Monto"
    writer = StatementWriter(path, header, columns)
    balance = opening
    for move in moves:
        balance += move.cents
        writer.row(
            [
                (40, f"{move.day:%Y-%m-%d}", "left"),
                (110, move.description, "left"),
                (430, "CR" if move.cents > 0 else "DB", "left"),
                (550, f"$ {_american(move.cents)}", "right"),
            ]
        )
    writer.finish(f"Saldo final $ {_american(balance)}")
    return balance


WRITERS = {"andino": write_andino, "sur": write_sur}


def generate(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for profile in PROFILES:
        rng = random.Random(f"{SEED}-{profile.slug}")
        balance = profile.opening_cents
        for year, month in profile.months:
            moves = sorted(profile.build(rng, year, month), key=lambda move: move.day)
            path = out / f"{profile.slug}-{year}-{month:02d}.pdf"
            balance = WRITERS[profile.bank](path, profile, moves, balance)
            files.append(path)
    rng = random.Random(f"{SEED}-heavy")
    heavy_moves = sorted(heavy(rng, 2026, 10), key=lambda move: move.day)
    heavy_path = out / "carga-pesada-2026-10.pdf"
    wholesaler = Profile("carga", "COMERCIO MAYORISTA", "andino", 0, heavy)
    write_andino(heavy_path, wholesaler, heavy_moves, 0)
    files.append(heavy_path)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("output"))
    for path in generate(parser.parse_args().out):
        print(path)


if __name__ == "__main__":
    main()
