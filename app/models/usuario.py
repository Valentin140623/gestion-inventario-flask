"""
Modelo Usuario y sistema de roles y permisos.

Aquí se implementa el requisito 1 del enunciado: "Sistema de registro y control
de acceso" con "distintos roles con permisos diferenciados".
"""

import enum
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, login_manager


class RolUsuario(enum.Enum):
    """
    Roles disponibles en la aplicación.

    Usamos un Enum en lugar de cadenas sueltas ("admin", "almacen"...) porque:
      - Si escribimos mal un rol, Python falla al instante en vez de crear
        silenciosamente un rol inexistente.
      - El editor nos autocompleta los valores.
      - Queda documentado en un único sitio cuáles son los roles válidos.
    """

    ADMIN = "Administrador"
    ALMACEN = "Responsable de almacén"
    FINANCIERO = "Responsable financiero"


# ---------------------------------------------------------------------------
# Matriz de permisos
# ---------------------------------------------------------------------------
# En lugar de escribir por todo el código "if usuario.rol == ADMIN or ...",
# definimos QUÉ puede hacer cada rol en un único diccionario. Así, cambiar los
# permisos de un rol es tocar una línea, no rastrear todo el proyecto.
#
# Cada permiso tiene la forma "recurso.acción".
PERMISOS_POR_ROL = {
    RolUsuario.ADMIN: {
        # El administrador tiene acceso total: gestiona usuarios, productos,
        # proveedores y ve toda la información financiera.
        "usuarios.gestionar",
        "productos.ver", "productos.editar",
        "proveedores.ver", "proveedores.editar",
        "inventario.ver", "inventario.editar",
        "ventas.ver", "ventas.registrar",
        "compras.ver", "compras.registrar",
        "analisis.ver", "analisis.financiero",
        "informes.generar",
    },
    RolUsuario.ALMACEN: {
        # El responsable de almacén trabaja con el stock: da de alta productos,
        # registra entradas/salidas y ventas, y consulta proveedores.
        # NO accede a la información financiera sensible (márgenes, beneficios)
        # ni a la gestión de usuarios.
        "productos.ver", "productos.editar",
        "proveedores.ver", "proveedores.editar",
        "inventario.ver", "inventario.editar",
        "ventas.ver", "ventas.registrar",
        "compras.ver", "compras.registrar",
        "analisis.ver",
        "informes.generar",
    },
    RolUsuario.FINANCIERO: {
        # El responsable financiero analiza: ve márgenes, rentabilidad y
        # beneficios, y genera informes. Es un rol de SOLO LECTURA: no puede
        # modificar stock, productos ni usuarios.
        "productos.ver",
        "proveedores.ver",
        "inventario.ver",
        "ventas.ver",
        "compras.ver",
        "analisis.ver", "analisis.financiero",
        "informes.generar",
    },
}


class Usuario(UserMixin, db.Model):
    """
    Usuario de la aplicación.

    Hereda de dos clases (herencia múltiple, concepto de POO):
      - UserMixin: le añade gratis los métodos que Flask-Login necesita
        (is_authenticated, get_id...). Nos ahorra escribirlos a mano.
      - db.Model: convierte esta clase en una tabla de la base de datos.
    """

    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)

    # unique=True crea un índice único: la base de datos misma impide que se
    # registren dos usuarios con el mismo email.
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)

    # Guardamos el HASH de la contraseña, NUNCA la contraseña original.
    # 255 caracteres porque el hash scrypt de Werkzeug es largo.
    password_hash = db.Column(db.String(255), nullable=False)

    # El rol se almacena como texto en la BD, pero al leerlo SQLAlchemy nos
    # devuelve directamente un miembro del Enum RolUsuario.
    rol = db.Column(db.Enum(RolUsuario), nullable=False, default=RolUsuario.ALMACEN)

    # Permite desactivar un usuario sin borrarlo (así conservamos el histórico
    # de las ventas que registró).
    activo = db.Column(db.Boolean, nullable=False, default=True)

    fecha_alta = db.Column(db.DateTime, nullable=False, default=datetime.now)
    ultimo_acceso = db.Column(db.DateTime, nullable=True)

    # Relaciones inversas: desde un usuario podemos ver las ventas y compras
    # que ha registrado. back_populates enlaza los dos lados de la relación.
    ventas = db.relationship("Venta", back_populates="usuario")
    compras = db.relationship("Compra", back_populates="usuario")
    movimientos = db.relationship("MovimientoInventario", back_populates="usuario")

    # -- Gestión de la contraseña ------------------------------------------

    def set_password(self, password_plano):
        """
        Cifra la contraseña y guarda el hash.

        generate_password_hash usa scrypt: una función de hash lenta y con
        "sal" aleatoria. Lenta a propósito, para que un atacante que robe la
        base de datos no pueda probar millones de contraseñas por segundo.
        Como la sal es aleatoria, dos usuarios con la misma contraseña tienen
        hashes distintos.
        """
        self.password_hash = generate_password_hash(password_plano)

    def check_password(self, password_plano):
        """
        Comprueba si la contraseña introducida es correcta.

        No se puede "descifrar" el hash: lo que se hace es volver a cifrar lo
        que ha escrito el usuario (con la misma sal) y comparar los resultados.
        Devuelve True o False.
        """
        return check_password_hash(self.password_hash, password_plano)

    # -- Control de accesos -------------------------------------------------

    def tiene_permiso(self, permiso):
        """
        Devuelve True si el rol de este usuario incluye el permiso indicado.

        Ejemplo:  usuario.tiene_permiso("productos.editar")

        Un usuario desactivado no tiene ningún permiso, aunque su rol lo
        contemple.

        Nota sobre "is False": comparamos explícitamente con False en lugar de
        escribir "if not self.activo". El motivo es que los valores default de
        las columnas (default=True) solo los aplica SQLAlchemy al INSERTAR la
        fila en la base de datos. En un objeto Usuario recién creado y todavía
        no guardado, self.activo vale None, y "not None" sería True: el usuario
        se quedaría sin ningún permiso. Con "is False" distinguimos las dos
        situaciones: desactivado a propósito (False) frente a aún sin guardar
        (None).
        """
        if self.activo is False:
            return False
        return permiso in PERMISOS_POR_ROL.get(self.rol, set())

    @property
    def es_admin(self):
        """Atajo cómodo para las plantillas HTML."""
        return self.rol == RolUsuario.ADMIN

    @property
    def is_active(self):
        """
        Sobrescribimos la propiedad de UserMixin (que siempre devuelve True).

        Flask-Login consulta is_active al hacer login_user(): así, un usuario
        marcado como inactivo no puede iniciar sesión aunque acierte la
        contraseña.
        """
        return self.activo is not False

    def __repr__(self):
        """Representación legible del objeto, útil al depurar."""
        return f"<Usuario {self.email} ({self.rol.value})>"


@login_manager.user_loader
def cargar_usuario(user_id):
    """
    Función que Flask-Login llama en CADA petición.

    En la cookie de sesión solo se guarda el id del usuario (nunca sus datos).
    Flask-Login nos pasa ese id como texto y nosotros devolvemos el objeto
    Usuario correspondiente, que quedará disponible como current_user.
    """
    return db.session.get(Usuario, int(user_id))
