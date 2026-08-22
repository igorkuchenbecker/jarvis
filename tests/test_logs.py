import json
import logging
from pathlib import Path

from jarvis.observability.logs import configurar_logging, obter_logger


def test_configurar_logging_grava_json_no_arquivo(tmp_path: Path) -> None:
    configurar_logging(diretorio_logs=tmp_path, nivel=logging.INFO)
    logger = obter_logger("teste")

    logger.info("mensagem de teste")

    conteudo = (tmp_path / "jarvis.log").read_text(encoding="utf-8").strip()
    registro = json.loads(conteudo)

    assert registro["mensagem"] == "mensagem de teste"
    assert registro["nivel"] == "INFO"
    assert registro["modulo"] == "jarvis.teste"
