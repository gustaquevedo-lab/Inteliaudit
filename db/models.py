import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, Integer, BigInteger, ForeignKey, DateTime, func, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base

def _uuid():
    import uuid
    return str(uuid.uuid4())

# ============================================================
#  MULTI-TENANCY: FIRMAS Y USUARIOS
# ============================================================

class Firma(Base):
    """Firma auditora — tenant raíz del SaaS."""
    __tablename__ = "firmas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    ruc: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    logo_path: Mapped[Optional[str]] = mapped_column(Text)
    eslogan: Mapped[Optional[str]] = mapped_column(Text)
    # 'trial' | 'starter' | 'professional' | 'enterprise'
    plan: Mapped[str] = mapped_column(String(20), default="trial")
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_hasta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="firma", cascade="all, delete-orphan")
    clientes: Mapped[list["Cliente"]] = relationship(back_populates="firma", cascade="all, delete-orphan")
    auditorias: Mapped[list["Auditoria"]] = relationship(back_populates="firma", cascade="all, delete-orphan")


class Usuario(Base):
    """Auditor o administrador de una firma."""
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # 'super_admin' | 'admin' | 'auditor_senior' | 'auditor'
    rol: Mapped[str] = mapped_column(String(30), default="auditor")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar_path: Mapped[Optional[str]] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_acceso: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    firma: Mapped["Firma"] = relationship(back_populates="usuarios")


# ============================================================
#  CLIENTES
# ============================================================

class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        UniqueConstraint("firma_id", "ruc"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    ruc: Mapped[str] = mapped_column(String(20), nullable=False)
    razon_social: Mapped[str] = mapped_column(Text, nullable=False)
    nombre_fantasia: Mapped[Optional[str]] = mapped_column(Text)
    actividad_principal: Mapped[Optional[str]] = mapped_column(Text)
    regimen: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_contribuyente: Mapped[Optional[str]] = mapped_column(String(20))
    direccion: Mapped[Optional[str]] = mapped_column(Text)
    email_dnit: Mapped[Optional[str]] = mapped_column(String(100))
    clave_marangatu: Mapped[Optional[str]] = mapped_column(Text)
    estado_dnit: Mapped[str] = mapped_column(String(20), default="activo")
    fecha_inscripcion: Mapped[Optional[str]] = mapped_column(String(10))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    firma: Mapped["Firma"] = relationship(back_populates="clientes")
    auditorias: Mapped[list["Auditoria"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")


# ============================================================
#  AUDITORÍAS
# ============================================================

class Auditoria(Base):
    __tablename__ = "auditorias"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    cliente_id: Mapped[str] = mapped_column(String(36), ForeignKey("clientes.id"), nullable=False)
    periodo_desde: Mapped[str] = mapped_column(String(7), nullable=False)
    periodo_hasta: Mapped[str] = mapped_column(String(7), nullable=False)
    tipo_encargo: Mapped[str] = mapped_column(String(50), default="auditoria_anual") 
    impuestos: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    materialidad: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(20), default="en_progreso")
    auditor: Mapped[Optional[str]] = mapped_column(String(200))
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fecha_cierre: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notas: Mapped[Optional[str]] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    firma: Mapped["Firma"] = relationship(back_populates="auditorias")
    cliente: Mapped["Cliente"] = relationship(back_populates="auditorias")
    hallazgos: Mapped[list["Hallazgo"]] = relationship(back_populates="auditoria", cascade="all, delete-orphan")
    tareas: Mapped[list["Tarea"]] = relationship(back_populates="auditoria", cascade="all, delete-orphan")
    declaraciones: Mapped[list["Declaracion"]] = relationship(back_populates="auditoria")
    declaraciones_juradas: Mapped[list["DeclaracionJurada"]] = relationship(back_populates="auditoria")
    cedulas: Mapped[list["Cedula"]] = relationship(back_populates="auditoria")
    informes: Mapped[list["Informe"]] = relationship(back_populates="auditoria")


# ============================================================
#  DECLARACIONES
# ============================================================

class Declaracion(Base):
    __tablename__ = "declaraciones"
    __table_args__ = (
        UniqueConstraint("firma_id", "cliente_id", "formulario", "periodo", "nro_rectificativa"),
        Index("idx_declaraciones_firma_periodo", "firma_id", "periodo"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("auditorias.id"))
    cliente_id: Mapped[str] = mapped_column(String(36), ForeignKey("clientes.id"), nullable=False)
    formulario: Mapped[str] = mapped_column(String(10), nullable=False)
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    fecha_presentacion: Mapped[str] = mapped_column(String(19), nullable=False)
    estado_declaracion: Mapped[str] = mapped_column(String(20), nullable=False)
    nro_rectificativa: Mapped[int] = mapped_column(Integer, default=0)
    datos_json: Mapped[str] = mapped_column(Text, nullable=False)
    archivo_pdf: Mapped[Optional[str]] = mapped_column(Text)
    descargado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    auditoria: Mapped[Optional["Auditoria"]] = relationship(back_populates="declaraciones")


class DeclaracionJurada(Base):
    """Resumen de declaraciones juradas para cruzamientos automáticos."""
    __tablename__ = "declaraciones_juradas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    cliente_id: Mapped[str] = mapped_column(String(36), ForeignKey("clientes.id"), nullable=False)
    auditoria_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("auditorias.id"))
    
    formulario: Mapped[str] = mapped_column(String(10))  # "120", "500", "700"
    periodo: Mapped[str] = mapped_column(String(7))     # YYYY-MM o YYYY
    numero_orden: Mapped[Optional[str]] = mapped_column(String(20))
    
    total_debito: Mapped[int] = mapped_column(BigInteger, default=0)
    total_credito: Mapped[int] = mapped_column(BigInteger, default=0)
    saldo_a_favor_contrib: Mapped[int] = mapped_column(BigInteger, default=0)
    saldo_a_favor_fisco: Mapped[int] = mapped_column(BigInteger, default=0)
    
    campos_json: Mapped[Optional[str]] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    auditoria: Mapped[Optional["Auditoria"]] = relationship(back_populates="declaraciones_juradas")


# ============================================================
#  RG 90
# ============================================================

class RG90(Base):
    __tablename__ = "rg90"
    __table_args__ = (
        Index("idx_rg90_firma_periodo", "firma_id", "periodo"),
        Index("idx_rg90_cdc", "cdc"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("auditorias.id"))
    cliente_id: Mapped[str] = mapped_column(String(36), ForeignKey("clientes.id"), nullable=False)
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    ruc_contraparte: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre_contraparte: Mapped[Optional[str]] = mapped_column(Text)
    timbrado: Mapped[Optional[str]] = mapped_column(String(20))
    establecimiento: Mapped[Optional[str]] = mapped_column(String(5))
    punto_expedicion: Mapped[Optional[str]] = mapped_column(String(5))
    nro_comprobante: Mapped[str] = mapped_column(String(20), nullable=False)
    cdc: Mapped[Optional[str]] = mapped_column(String(44))
    tipo_comprobante: Mapped[Optional[str]] = mapped_column(String(5))
    fecha_emision: Mapped[str] = mapped_column(String(10), nullable=False)
    base_gravada_10: Mapped[int] = mapped_column(Integer, default=0)
    base_gravada_5: Mapped[int] = mapped_column(Integer, default=0)
    monto_exento: Mapped[int] = mapped_column(Integer, default=0)
    iva_10: Mapped[int] = mapped_column(Integer, default=0)
    iva_5: Mapped[int] = mapped_column(Integer, default=0)
    iva_total: Mapped[int] = mapped_column(Integer, default=0)
    total_comprobante: Mapped[int] = mapped_column(Integer, default=0)
    cdc_valido: Mapped[Optional[bool]] = mapped_column(Boolean)
    ruc_activo: Mapped[Optional[bool]] = mapped_column(Boolean)
    en_sifen: Mapped[Optional[bool]] = mapped_column(Boolean)
    observaciones: Mapped[Optional[str]] = mapped_column(Text)
    fuente_archivo: Mapped[Optional[str]] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
#  SIFEN
# ============================================================

class SifenComprobante(Base):
    __tablename__ = "sifen_comprobantes"
    __table_args__ = (
        Index("idx_sifen_firma_cdc", "firma_id", "cdc"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("auditorias.id"))
    cdc: Mapped[str] = mapped_column(String(44), nullable=False)
    tipo_de: Mapped[str] = mapped_column(String(5), nullable=False)
    ruc_emisor: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre_emisor: Mapped[Optional[str]] = mapped_column(Text)
    ruc_receptor: Mapped[Optional[str]] = mapped_column(String(20))
    nombre_receptor: Mapped[Optional[str]] = mapped_column(Text)
    timbrado: Mapped[Optional[str]] = mapped_column(String(20))
    establecimiento: Mapped[Optional[str]] = mapped_column(String(5))
    punto_expedicion: Mapped[Optional[str]] = mapped_column(String(5))
    nro_comprobante: Mapped[Optional[str]] = mapped_column(String(20))
    fecha_emision: Mapped[str] = mapped_column(String(25), nullable=False)
    base_gravada_10: Mapped[int] = mapped_column(Integer, default=0)
    base_gravada_5: Mapped[int] = mapped_column(Integer, default=0)
    monto_exento: Mapped[int] = mapped_column(Integer, default=0)
    iva_total: Mapped[int] = mapped_column(Integer, default=0)
    total_comprobante: Mapped[int] = mapped_column(Integer, default=0)
    estado_sifen: Mapped[str] = mapped_column(String(20), default="aprobado")
    consultado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
#  HECHAUKA
# ============================================================

class Hechauka(Base):
    __tablename__ = "hechauka"
    __table_args__ = (
        Index("idx_hechauka_firma_periodo", "firma_id", "periodo"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("auditorias.id"))
    cliente_id: Mapped[str] = mapped_column(String(36), ForeignKey("clientes.id"), nullable=False)
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    ruc_informante: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre_informante: Mapped[Optional[str]] = mapped_column(Text)
    tipo_operacion: Mapped[str] = mapped_column(String(30), nullable=False)
    nro_comprobante: Mapped[Optional[str]] = mapped_column(String(30))
    fecha_comprobante: Mapped[Optional[str]] = mapped_column(String(10))
    monto_operacion: Mapped[int] = mapped_column(Integer, default=0)
    iva_operacion: Mapped[int] = mapped_column(Integer, default=0)
    retencion_iva: Mapped[int] = mapped_column(Integer, default=0)
    retencion_ire: Mapped[int] = mapped_column(Integer, default=0)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
#  HALLAZGOS
# ============================================================

class Hallazgo(Base):
    __tablename__ = "hallazgos"
    __table_args__ = (
        Index("idx_hallazgos_firma_riesgo", "firma_id", "nivel_riesgo", "estado"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[str] = mapped_column(String(36), ForeignKey("auditorias.id"), nullable=False)
    impuesto: Mapped[str] = mapped_column(String(20), nullable=False)
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    tipo_hallazgo: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion_tecnica: Mapped[Optional[str]] = mapped_column(Text)
    articulo_legal: Mapped[str] = mapped_column(Text, nullable=False)
    base_ajuste: Mapped[int] = mapped_column(Integer, default=0)
    impuesto_omitido: Mapped[int] = mapped_column(Integer, default=0)
    multa_estimada: Mapped[int] = mapped_column(Integer, default=0)
    intereses_estimados: Mapped[int] = mapped_column(Integer, default=0)
    total_contingencia: Mapped[int] = mapped_column(Integer, default=0)
    nivel_riesgo: Mapped[str] = mapped_column(String(10), default="medio")
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    notas_auditor: Mapped[Optional[str]] = mapped_column(Text)
    evidencias: Mapped[Optional[str]] = mapped_column(Text)  # JSON array
    creado_por: Mapped[str] = mapped_column(String(50), default="sistema")
    sugerencia_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    auditoria: Mapped["Auditoria"] = relationship(back_populates="hallazgos")


# ============================================================
#  TAREAS
# ============================================================

class Tarea(Base):
    __tablename__ = "tareas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[str] = mapped_column(String(36), ForeignKey("auditorias.id"), nullable=False)
    
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(String(50), default="general")
    completada: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_completado: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    auditoria: Mapped["Auditoria"] = relationship(back_populates="tareas")


# ============================================================
#  CEDULAS E INFORMES
# ============================================================

class Cedula(Base):
    __tablename__ = "cedulas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[str] = mapped_column(String(36), ForeignKey("auditorias.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    datos_json: Mapped[str] = mapped_column(Text, nullable=False)
    
    auditoria: Mapped["Auditoria"] = relationship(back_populates="cedulas")


class Informe(Base):
    __tablename__ = "informes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    auditoria_id: Mapped[str] = mapped_column(String(36), ForeignKey("auditorias.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[str] = mapped_column(String(20), default="generado")
    archivo_docx: Mapped[Optional[str]] = mapped_column(Text)
    archivo_pdf: Mapped[Optional[str]] = mapped_column(Text)
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    auditoria: Mapped["Auditoria"] = relationship(back_populates="informes")


class CredencialMarangatu(Base):
    """Credenciales de acceso a Marangatú para un cliente, guardadas cifradas."""
    __tablename__ = "credenciales_marangatu"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    cliente_ruc: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_dnit_enc: Mapped[str] = mapped_column(Text, nullable=False)   # cifrado
    clave_dnit_enc: Mapped[str] = mapped_column(Text, nullable=False)     # cifrado
    alias: Mapped[Optional[str]] = mapped_column(String(100))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("firma_id", "cliente_ruc"),
    )

class AuditTrail(Base):
    __tablename__ = "audit_trail"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firma_id: Mapped[str] = mapped_column(String(36), ForeignKey("firmas.id"), nullable=False)
    usuario_id: Mapped[Optional[str]] = mapped_column(String(36))
    auditoria_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("auditorias.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    modulo: Mapped[Optional[str]] = mapped_column(String(50))
    detalle: Mapped[Optional[str]] = mapped_column(Text)
    datos_json: Mapped[Optional[str]] = mapped_column(Text)
    resultado: Mapped[str] = mapped_column(String(20), default="ok")
