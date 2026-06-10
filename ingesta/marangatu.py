"""
Scraper de Marangatú — portal tributario DNIT Paraguay.
URL: https://marangatu.dnit.gov.py
Autenticación: RUC + clave de acceso DNIT.
No hay API pública; toda la interacción es vía Playwright.
"""
import asyncio
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from rich.console import Console

from config.settings import settings

console = Console()

BASE_URL = "https://marangatu.dnit.gov.py"
TIMEOUT = 60_000  # ms - aumentado para portal lento
MAX_RETRIES = 3
BACKOFF_BASE = 2  # segundos


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
        self._logged_in = False

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
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
            ],
        )
        self._context = await self._browser.new_context(
            accept_downloads=True,
            locale="es-PY",
            viewport={"width": 1920, "height": 1080},
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
        self._logged_in = False

    @property
    def page(self) -> Page:
        assert self._page is not None, "Browser no iniciado. Usar como context manager."
        return self._page

    async def _reintentar(self, func, *args, **kwargs):
        """Ejecuta una función con reintentos y backoff exponencial."""
        for intento in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if intento == MAX_RETRIES - 1:
                    raise
                wait = BACKOFF_BASE ** intento + random.uniform(0, 1)
                console.print(f"[yellow]⚠[/] Intento {intento + 1} falló: {e}. Reintentando en {wait:.1f}s...")
                await asyncio.sleep(wait)

    # --------------------------------------------------------
    #  Autenticación
    # --------------------------------------------------------

    async def login(self) -> None:
        """Inicia sesión en Marangatú con RUC y clave."""
        console.print(f"[blue]DNIT:[/] iniciando sesión para RUC {self.ruc}...")
        
        async def _login():
            await self.page.goto(f"{BASE_URL}/faces/jsp/login.jsp")
            await self.page.wait_for_load_state("networkidle")
            
            # Esperar formulario de login
            await self.page.wait_for_selector("input[name='loginForm:txtRuc']", timeout=TIMEOUT)
            
            # Completar formulario
            await self.page.fill("input[name='loginForm:txtRuc']", self.ruc)
            await self.page.fill("input[name='loginForm:txtClave']", self.clave)
            
            # Click en botón de ingresar
            await self.page.click("input[name='loginForm:btnIngresar']")
            
            # Esperar redirección al dashboard o menú principal
            await self.page.wait_for_load_state("networkidle")
            
            # Verificar que el login fue exitoso
            if "login.jsp" in self.page.url:
                raise Exception("Login falló - verificar credenciales")
            
            console.print("[green]✓[/] Sesión iniciada.")
            self._logged_in = True

        await self._reintentar(_login)

    async def _verificar_sesion(self) -> bool:
        """Retorna True si la sesión sigue activa."""
        try:
            await self.page.goto(f"{BASE_URL}/faces/jsp/menu.jsp")
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            return "menu.jsp" in self.page.url or "inicio" in self.page.url
        except Exception:
            return False

    async def _asegurar_sesion(self) -> None:
        """Verifica sesión y hace re-login si es necesario."""
        if not self._logged_in or not await self._verificar_sesion():
            console.print("[yellow]⚠[/] Sesión expirada, re-iniciando...")
            await self.login()

    # --------------------------------------------------------
    #  Navegación JSF helper
    # --------------------------------------------------------

    async def _navegar_jsf(self, url: str, wait_selector: Optional[str] = None) -> None:
        """Navega a una página JSF y espera a que cargue."""
        await self._asegurar_sesion()
        await self.page.goto(url)
        await self.page.wait_for_load_state("networkidle")
        if wait_selector:
            await self.page.wait_for_selector(wait_selector, timeout=TIMEOUT)

    # --------------------------------------------------------
    #  Datos del contribuyente
    # --------------------------------------------------------

    async def descargar_datos_contribuyente(self) -> dict:
        """Extrae datos del perfil del contribuyente desde Marangatú."""
        console.print("[blue]DNIT:[/] descargando datos del contribuyente...")
        
        async def _descargar():
            await self._navegar_jsf(
                f"{BASE_URL}/faces/jsp/contribuyente/datosContribuyente.jsp",
                "input[name*='txtRazonSocial']"
            )
            
            datos = {}
            
            # Extraer campos del formulario
            campos = {
                "ruc": "input[name*='txtRuc']",
                "razon_social": "input[name*='txtRazonSocial']",
                "nombre_fantasia": "input[name*='txtNombreFantasia']",
                "actividad_principal": "input[name*='txtActividad']",
                "direccion": "input[name*='txtDireccion']",
                "telefono": "input[name*='txtTelefono']",
                "email": "input[name*='txtEmail']",
                "estado": "input[name*='txtEstado']",
                "fecha_inscripcion": "input[name*='txtFechaInscripcion']",
            }
            
            for campo, selector in campos.items():
                try:
                    elemento = await self.page.query_selector(selector)
                    if elemento:
                        valor = await elemento.get_attribute("value")
                        datos[campo] = valor or ""
                except Exception:
                    datos[campo] = ""
            
            return datos

        return await self._reintentar(_descargar)

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
        """
        console.print("[blue]DNIT:[/] listando declaraciones...")
        
        async def _listar():
            await self._navegar_jsf(
                f"{BASE_URL}/faces/jsp/declaraciones/misDeclaraciones.jsp",
                "table[id*='tblDeclaraciones']"
            )
            
            # Aplicar filtros si se proporcionan
            if formulario:
                await self.page.select_option(
                    "select[name*='selFormulario']",
                    value=formulario
                )
            
            if periodo_desde:
                await self.page.fill(
                    "input[name*='txtPeriodoDesde']",
                    periodo_desde.replace("-", "/")
                )
            
            if periodo_hasta:
                await self.page.fill(
                    "input[name*='txtPeriodoHasta']",
                    periodo_hasta.replace("-", "/")
                )
            
            # Click en buscar
            await self.page.click("input[name*='btnBuscar']")
            await self.page.wait_for_load_state("networkidle")
            
            # Parsear tabla de resultados
            declaraciones = []
            rows = await self.page.query_selector_all("table[id*='tblDeclaraciones'] tbody tr")
            
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) >= 5:
                    declaracion = {
                        "formulario": await cells[0].inner_text(),
                        "periodo": await cells[1].inner_text(),
                        "fecha_presentacion": await cells[2].inner_text(),
                        "estado_declaracion": await cells[3].inner_text(),
                        "nro_rectificativa": await cells[4].inner_text(),
                    }
                    
                    # Extraer URL del PDF si existe
                    link = await cells[-1].query_selector("a")
                    if link:
                        declaracion["url_pdf"] = await link.get_attribute("href")
                    
                    declaraciones.append(declaracion)
            
            return declaraciones

        return await self._reintentar(_listar)

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
        """
        console.print(f"[blue]DNIT:[/] descargando RG90 período {periodo}...")
        destino = self.storage_path / "rg90" / f"rg90_{periodo}.xlsx"
        destino.parent.mkdir(parents=True, exist_ok=True)

        async def _descargar():
            await self._navegar_jsf(
                f"{BASE_URL}/faces/jsp/declaraciones/rg90.jsp",
                "select[name*='selPeriodo']"
            )
            
            # Seleccionar período
            periodo_formateado = periodo.replace("-", "/")
            await self.page.select_option(
                "select[name*='selPeriodo']",
                label=periodo_formateado
            )
            
            # Click en exportar
            async with self.page.expect_download() as download_info:
                await self.page.click("input[name*='btnExportar'], button:has-text('Exportar')")
            
            download = await download_info.value
            await download.save_as(str(destino))
            console.print(f"[green]✓[/] RG90 descargado: {destino.name}")
            return destino

        return await self._reintentar(_descargar)

    async def descargar_rg90_rango(self, periodo_desde: str, periodo_hasta: str) -> list[Path]:
        """Descarga RG90 para un rango de períodos. Retorna lista de paths."""
        periodos = _generar_periodos(periodo_desde, periodo_hasta)
        archivos = []
        for periodo in periodos:
            try:
                archivo = await self.descargar_rg90(periodo)
                archivos.append(archivo)
                await asyncio.sleep(2)  # cortesía al portal
            except Exception as e:
                console.print(f"[yellow]⚠[/] Error descargando RG90 {periodo}: {e}")
        return archivos

    # --------------------------------------------------------
    #  HECHAUKA
    # --------------------------------------------------------

    async def descargar_hechauka(self, periodo: str) -> Path:
        """
        Descarga el XLSX de HECHAUKA (información declarada por terceros) para un período.
        """
        console.print(f"[blue]DNIT:[/] descargando HECHAUKA período {periodo}...")
        destino = self.storage_path / "hechauka" / f"hechauka_{periodo}.xlsx"
        destino.parent.mkdir(parents=True, exist_ok=True)

        async def _descargar():
            await self._navegar_jsf(
                f"{BASE_URL}/faces/jsp/hechauka/informacionRecibida.jsp",
                "select[name*='selPeriodo']"
            )
            
            # Seleccionar período
            periodo_formateado = periodo.replace("-", "/")
            await self.page.select_option(
                "select[name*='selPeriodo']",
                label=periodo_formateado
            )
            
            # Click en exportar
            async with self.page.expect_download() as download_info:
                await self.page.click("input[name*='btnExportar'], button:has-text('Exportar')")
            
            download = await download_info.value
            await download.save_as(str(destino))
            console.print(f"[green]✓[/] HECHAUKA descargado: {destino.name}")
            return destino

        return await self._reintentar(_descargar)

    # --------------------------------------------------------
    #  Estado de Cuenta
    # --------------------------------------------------------

    async def descargar_estado_cuenta(self, impuesto: Optional[str] = None) -> Path:
        """
        Descarga el estado de cuenta DNIT (deudas, pagos, saldos).
        """
        console.print("[blue]DNIT:[/] descargando estado de cuenta...")
        destino = self.storage_path / "estado_cuenta" / "estado_cuenta.pdf"
        destino.parent.mkdir(parents=True, exist_ok=True)

        async def _descargar():
            await self._navegar_jsf(
                f"{BASE_URL}/faces/jsp/estadoCuenta/estadoCuenta.jsp",
                "select[name*='selImpuesto']"
            )
            
            # Aplicar filtro de impuesto si se proporciona
            if impuesto:
                await self.page.select_option(
                    "select[name*='selImpuesto']",
                    label=impuesto
                )
            
            # Click en descargar
            async with self.page.expect_download() as download_info:
                await self.page.click("input[name*='btnDescargar'], button:has-text('Descargar')")
            
            download = await download_info.value
            await download.save_as(str(destino))
            console.print(f"[green]✓[/] Estado de cuenta descargado")
            return destino

        return await self._reintentar(_descargar)

    # --------------------------------------------------------
    #  Validación de RUC
    # --------------------------------------------------------

    async def verificar_ruc(self, ruc: str) -> dict:
        """
        Verifica el estado de un RUC en el portal DNIT.
        Usa el portal público, no requiere login.
        """
        console.print(f"[blue]DNIT:[/] verificando RUC {ruc}...")
        
        async def _verificar():
            # Portal público de consulta de RUC
            await self.page.goto(
                "https://www.dnit.gov.py/portal/PARAGUAY-DNIT/InformacionTributaria"
            )
            await self.page.wait_for_load_state("networkidle")
            
            # Buscar campo de RUC e ingresar
            await self.page.fill("input[name*='txtRuc']", ruc)
            await self.page.click("input[name*='btnBuscar'], button:has-text('Buscar')")
            await self.page.wait_for_load_state("networkidle")
            
            # Extraer datos
            datos = {"ruc": ruc}
            
            campos = {
                "razon_social": "input[name*='txtRazonSocial']",
                "estado": "input[name*='txtEstado']",
                "fecha_inscripcion": "input[name*='txtFechaInscripcion']",
            }
            
            for campo, selector in campos.items():
                try:
                    elemento = await self.page.query_selector(selector)
                    if elemento:
                        valor = await elemento.get_attribute("value")
                        datos[campo] = valor or ""
                except Exception:
                    datos[campo] = ""
            
            return datos

        return await self._reintentar(_verificar)


# --------------------------------------------------------
#  Helpers
# --------------------------------------------------------

def _generar_periodos(desde: str, hasta: str) -> list[str]:
    """
    Genera lista de períodos YYYY-MM entre dos fechas inclusive.
    Ej: _generar_periodos("2024-01", "2024-03") → ["2024-01", "2024-02", "2024-03"]
    """
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
