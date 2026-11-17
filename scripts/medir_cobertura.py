"""Mede cobertura da lógica no computador; não mede tempos da ESP32."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcc", default=shutil.which("gcc") or
                        "C:/Program Files/CodeBlocks/MinGW/bin/gcc.exe")
    args = parser.parse_args()
    gcc = Path(args.gcc).resolve()
    gcov = gcc.with_name("gcov.exe" if os.name == "nt" else "gcov")
    if not gcc.is_file() or not gcov.is_file():
        parser.error("Informe --gcc com o caminho de um GCC acompanhado de gcov.")
    work = root / "build/coverage"
    output = root / "dados/cobertura"
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(gcc.parent) + os.pathsep + str(gcc.parent.parent.parent) + os.pathsep + env["PATH"]
    # Remove somente contadores gerados por este script, sem acumular execuções.
    for name in ("huffman.gcda", "test_huffman.gcda"):
        (work / name).unlink(missing_ok=True)
    transcript = []

    def run(command):
        result = subprocess.run([str(x) for x in command], cwd=work, env=env,
                                text=True, capture_output=True, errors="replace")
        transcript.append("$ " + " ".join(map(str, command)) + "\n" +
                          result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(transcript[-1])
        return result.stdout

    version = run([gcc, "--version"]).splitlines()[0]
    flags = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-O0", "--coverage", "-I", "../../main"]
    run([gcc, *flags, "-c", "../../main/huffman.c", "-o", "huffman.o"])
    run([gcc, *flags, "-c", "../../tests/test_huffman.c", "-o", "test_huffman.o"])
    executable = work / "test_huffman.exe"
    run([gcc, "--coverage", "huffman.o", "test_huffman.o", "-o", executable])
    test_output = run([executable])
    report = run([gcov, "-b", "-c", "huffman.gcno"])
    summary = {
        "escopo": "main/huffman.c; testes no computador Windows, nao na ESP32",
        "compilador": version,
        "opcoes": flags,
        "linhas_percentual": float(re.search(r"Lines executed:([\d.]+)%", report)[1]),
        "desvios_executados_percentual": float(re.search(r"Branches executed:([\d.]+)%", report)[1]),
        "desvios_tomados_percentual": float(re.search(r"Taken at least once:([\d.]+)%", report)[1]),
        "observacao": "Cobertura de desvio usa Taken at least once; Branches executed nao significa ambos os resultados tomados.",
        "sha256": {},
    }
    for name in ("main/huffman.c", "main/huffman.h", "tests/test_huffman.c"):
        content = (root / name).read_bytes()
        summary["sha256"][name] = hashlib.sha256(content).hexdigest()
        destination = output / "fontes" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    (output / "huffman.c.gcov").write_bytes((work / "huffman.c.gcov").read_bytes())
    (output / "execucao.txt").write_text("\n".join(transcript), encoding="utf-8")
    (output / "resumo.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(test_output + report)
    print("Evidencias salvas em dados/cobertura.")


if __name__ == "__main__":
    main()
