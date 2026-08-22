import pytest

from jarvis.security.allowlist import ErroForaDaAllowlist, validar_binario_permitido


def test_aceita_binario_na_allowlist() -> None:
    validar_binario_permitido("git", ("git", "ls"))


def test_recusa_binario_fora_da_allowlist() -> None:
    with pytest.raises(ErroForaDaAllowlist, match="não está na allowlist"):
        validar_binario_permitido("curl", ("git", "ls"))


@pytest.mark.parametrize("binario", ["sudo", "su", "doas", "pkexec"])
def test_recusa_binarios_de_escalonamento_mesmo_se_estiverem_na_allowlist(binario: str) -> None:
    with pytest.raises(ErroForaDaAllowlist, match="proibido sempre"):
        validar_binario_permitido(binario, (binario,))
