"""
Pacote core do ByteForge.

Contém toda a lógica de backend da aplicação, desacoplada da interface
gráfica (GUI). Nenhum módulo deste pacote deve importar customtkinter
ou qualquer biblioteca de interface, garantindo a separação de
responsabilidades (Model/Logic vs View).
"""

__all__ = [
    "disk_utils",
    "file_generator",
    "network_utils",
    "plugin_manager",
]
