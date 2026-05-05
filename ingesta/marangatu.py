"""
Scraper de Marangatú — portal tributario SET Paraguay.
URL: https://marangatu.set.gov.py
Autenticación: RUC + clave de acceso SET.
No hay API pública; toda la interacción es vía Playwright.
"""
import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from rich.console import Console

from config.settings import settings

console = Console()

BASE_URL = "https://marangatu.set.gov.py"
TIMEOUT = 30_000  # ms


class MarangatuScraper:
    """
    Maneja el ciclo de vida del browser y todas las operaciones
    de descarga desde el portal Marangatú.
    """

    def __init__(self, ruc: str, clave: str, storage_path: Optional[Path] = None):
        self.ruc = ruc
        self.clave = clave
        self.storage_path = storage_path or Path(settings.storage_path) / ruc
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "MarangatuScraper":
        await self._iniciar_browser()
        await self.login()
        return self

    async def __aexit__(self, *_) -> None:
        await self.cerrar()

    # --------------------------------------------------------
    #  Browser lifecycle
    # --------------------------------------------------------

    async def _iniciar_browser(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._context = await self._browser.new_context(
            accept_downloads=True,
            locale="es-PY",
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(TIMEOUT)

    async def cerrar(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def page(self) -> Page:
        assert self._page is not None, "Browser no iniciado. Usar como context manager."
        return self._page

    # --------------------------------------------------------
    #  Autenticación
    # --------------------------------------------------------

    async def login(self) -> None:
        """Inicia sesión en Marangatú con RUC y clave."""
        console.print(f"[blue]Marangatú:[/] iniciando sesión para RUC {self.ruc}...")
        await self.page.goto(f"{BASE_URL}/index.xhtml")

        # TODO: ajustar selectores reales del formulario de login
        await self.page.fill("#formLogin\\:ruc", self.ruc)
        await self.page.fill("#formLogin\\:clave", self.clave)
        await self.page.click("#formLogin\\:btnIngresar")

        # Esperar redirección al dashboard
        await self.page.wait_for_url(f"{BASE_URL}/inicio.xhtml", timeout=TIMEOUT)
        console.print("[green]✓[/] Sesión iniciada.")

    async def _verificar_sesion(self) -> bool:
        """Retorna True si la sesión sigue activa."""
        try:
            await self.page.goto(f"{BASE_URL}/inicio.xhtml")
            return "inicio.xhtml" in self.page.url
        except Exception:
            return False

    # --------------------------------------------------------
    #  Datos del contribuyente
    # --------------------------------------------------------

    async def descargar_datos_contribuyente(self) -> dict:
        """Extrae datos del perfil del contribuyente desde Marangatú."""
        console.print("[blue]Marangatú:[/] descargando datos del contribuyente...")
        # TODO: navegar a sección Datos del Contribuyente y parsear
        # await self.page.goto(f"{BASE_URL}/contribuyente/datos.xhtml")
        raise NotImplementedError("Implementar selectores de la sección Datos del Contribuyente")

    # --------------------------------------------------------
    #  Declaraciones Juradas
    # --------------------------------------------------------

    async def listar_declaraciones(
        self,
        formulario: Optional[str] = None,
        periodo_desde: Optional[str] = None,
        periodo_hasta: Optional[str] = None,
    ) -> list[dict]:
        """
        Lista todas las DJ presentadas.
        Navega a Declaraciones > Mis Declaraciones.

        Returns:
            Lista de dicts con keys: formulario, periodo, fecha_presentacion,
            estado_declaracion, nro_rectificativa, url_pdf
        """
        console.print("[blue]Marangatú:[/] listando declaraciones...")
        # TODO: navegar a Declaraciones > Mis Declaraciones
        # Aplicar filtros de formulario y período si se proporcionan
        # Parsear tabla de resultados con playwright
        raise NotImplementedError("Implementar navegación a Mis Declaraciones")

    async def descargar_declaracion_pdf(self, url_pdf: str, nombre_archivo: str) -> Path:
        """Descarga el PDF de una declaración jurada."""
        destino = self.storage_path / "declaraciones" / nombre_archivo
        destino.parent.mkdir(parents=True, exist_ok=True)

        async with self.page.expect_download() as download_info:
            await self.page.goto(url_pdf)
        download = await download_info.value
        await download.save_as(str(destino))
        return destino

    # --------------------------------------------------------
    #  RG 90
    # --------------------------------------------------------

    async def descargar_rg90(self, periodo: str) -> Path:
        """
        Descarga el XLSX de RG90 (comprobantes declarados en IVA) para un período.

        Args:
            periodo: formato YYYY-MM (ej: "2024-03")

        Returns:
            Path al archivo XLSX descargado.
        """
        console.print(f"[blue]Marangatú:[/] descargando RG90 período {periodo}...")
        destino = self.storage_path / "rg90" / f"rg90_{periodo}.xlsx"
        destino.parent.mkdir(parents=True, exist_ok=True)

        # TODO: navegar a Declaraciones > RG 90, seleccionar período, descargar XLSX
        # La URL exacta y los selectores dependen del portal actual
        raise NotImplementedError("Implementar descarga RG90 desde Marangatú")

        return destino  # noqa: unreachable

    async def descargar_rg90_rango(self, periodo_desde: str, periodo_hasta: str) -> list[Path]:
        """Descarga RG90 para un rango de períodos. Retorna lista de paths."""
        periodos = _generar_periodos(periodo_desde, periodo_hasta)
        archivos = []
        for periodo in periodos:
            try:
                archivo = await self.descargar_rg90(periodo)
                archivos.append(archivo)
                await asyncio.sleep(1)  # cortesía al portal
            except Exception as e:
                console.print(f"[yellow]⚠[/] Error descargando RG90 {periodo}: {e}")
        return archivos

    # --------------------------------------------------------
    #  HECHAUKA
    # --------------------------------------------------------

    async def descargar_hechauka(self, periodo: str) -> Path:
        """
        Descarga el XLSX de HECHAUKA (información declarada por terceros) para un período.

        Args:
            periodo: formato YYYY-MM

        Returns:
            Path al archivo XLSX descargado.
        """
        console.print(f"[blue]Marangatú:[/] descargando HECHAUKA período {periodo}...")
        destino = self.storage_path / "hechauka" / f"hechauka_{periodo}.xlsx"
        destino.parent.mkdir(parents=True, exist_ok=True)

        # TODO: navegar a HECHAUKA > Información Recibida, seleccionar período, descargar
        raise NotImplementedError("Implementar descarga HECHAUKA desde Marangatú")

        return destino  # noqa: unreachable

    # --------------------------------------------------------
    #  Estado de Cuenta
    # --------------------------------------------------------

    async def descargar_estado_cuenta(self, impuesto: Optional[str] = None) -> Path:
        """
        Descarga el estado de cuenta SET (deudas, pagos, saldos).

        Returns:
            Path al PDF descargado.
        """
        console.print("[blue]Marangatú:[/] descargando estado de cuenta...")
        destino = self.storage_path / "estado_cuenta" / "estado_cuenta.pdf"
        destino.parent.mkdir(parents=True, exist_ok=True)

        # TODO: navegar a Estado de Cuenta, aplicar filtros, descargar PDF
        raise NotImplementedError("Implementar descarga Estado de Cuenta")

        return destino  # noqa: unreachable

    # --------------------------------------------------------
    #  Validación de RUC
    # --------------------------------------------------------

    async def verificar_ruc(self, ruc: str) -> dict:
        """
        Verifica el estado de un RUC en el portal SET.

        Returns:
            Dict con keys: ruc, razon_social, estado, fecha_inscripcion
        """
        # TODO: la consulta de RUC puede hacerse en el portal público
        # https://www.set.gov.py/portal/PARAGUAY-SET/InformacionTributaria?leafId=ruc
        raise NotImplementedError("Implementar verificación de RUC")


# --------------------------------------------------------
#  Helpers
# --------------------------------------------------------

def _generar_periodos(desde: str, hasta: str) -> list[str]:
    """
    Genera lista de períodos YYYY-MM entre dos fechas inclusive.
    Ej: _generar_periodos("2024-01", "2024-03") → ["2024-01", "2024-02", "2024-03"]
    """
    from datetime import date

    año_d, mes_d = int(desde[:4]), int(desde[5:7])
    año_h, mes_h = int(hasta[:4]), int(hasta[5:7])

    periodos = []
    año, mes = año_d, mes_d
    while (año, mes) <= (año_h, mes_h):
        periodos.append(f"{año:04d}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes = 1
            año += 1
    return periodos
