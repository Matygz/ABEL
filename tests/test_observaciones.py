"""Prueba de persistencia idempotente. Ejecutar: python -m tests.test_observaciones"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid7

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from protocolos.contenidos import Observacion


async def main():
    repo = Repositorio(cargar_config())

    dispositivos = await repo.listar_dispositivos()
    device_id = dispositivos[0]["id"]
    print("usando dispositivo:", dispositivos[0]["name"])

    obs = [
        Observacion(uuid7(), datetime.now(timezone.utc), "presence_mark",
                    {"uptime_seconds": 10.0 * i})
        for i in range(3)
    ]
    obs.append(
        Observacion(uuid7(), datetime.now(timezone.utc), "tipo_inventado", {})
    )

    ok, mal = await repo.persistir_observaciones(device_id, obs)
    print(f"primera vez  -> confirmadas: {len(ok)}, rechazadas: {len(mal)}")

    ok2, mal2 = await repo.persistir_observaciones(device_id, obs)
    print(f"reenvío      -> confirmadas: {len(ok2)}, rechazadas: {len(mal2)}")

    assert ok == ok2, "El reenvío debe confirmar lo mismo."
    print("\nidempotencia ok: el reenvío no duplicó nada.")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)