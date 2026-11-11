import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_statements import PROFILES, generate  # noqa: E402


def test_same_seed_gives_the_same_movements():
    student = PROFILES[0]

    first = student.build(random.Random("seed"), 2026, 10)
    second = student.build(random.Random("seed"), 2026, 10)

    assert first == second


def test_october_hides_the_planted_findings():
    descriptions = {
        profile.slug: [move.description for move in profile.build(random.Random(1), 2026, 10)]
        for profile in PROFILES
    }

    assert "AMAZON COMPRA CONSOLA" in descriptions["estudiante"]
    assert descriptions["freelancer"].count("NETFLIX COM") == 2
    assert "COMISION SOBREGIRO" in descriptions["pyme"]
    assert "TALLER MECANICO MOTOR" in descriptions["conductor"]
    assert descriptions["docente"].count("SMARTFIT MEMBRESIA") == 2
    assert "AVIANCA TIQUETES INTERNACIONALES" in descriptions["medica"]
    assert "COMISION TRANSFERENCIA INTERNACIONAL" in descriptions["emprendedora"]
    assert descriptions["disenadora"].count("ADOBE CREATIVE CLOUD") == 2
    assert "MACBOOK PRO TIENDA APPLE" in descriptions["disenadora"]


def test_writes_one_pdf_per_profile_and_month(tmp_path):
    files = generate(tmp_path)

    assert len(files) == sum(len(profile.months) for profile in PROFILES) + 1
    assert all(path.read_bytes().startswith(b"%PDF-") for path in files)


def test_output_is_reproducible(tmp_path):
    first = [path.read_bytes() for path in generate(tmp_path / "a")]
    second = [path.read_bytes() for path in generate(tmp_path / "b")]

    assert first == second
