"""Paquete de formularios de la aplicación."""

from .auth import FormularioLogin, FormularioRegistro
from .producto import FormularioCategoria, FormularioProducto
from .proveedor import FormularioAsociarProducto, FormularioProveedor
from .usuario import FormularioUsuario

__all__ = [
    "FormularioLogin",
    "FormularioRegistro",
    "FormularioProducto",
    "FormularioCategoria",
    "FormularioProveedor",
    "FormularioAsociarProducto",
    "FormularioUsuario",
]
