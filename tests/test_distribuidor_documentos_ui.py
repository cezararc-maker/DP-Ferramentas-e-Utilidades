import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from dp_ferramentas.distribuidor_documentos_ui import DistribuidorDocumentosWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_analysis_table_explains_columns_and_keeps_headers_visible():
    app = _app()
    window = DistribuidorDocumentosWindow()
    window.show()
    app.processEvents()

    expected = [
        "Arquivo de origem",
        "Tipo identificado",
        "Colaborador identificado",
        "Destino completo",
        "Resultado da análise",
    ]
    assert [window.table.horizontalHeaderItem(i).text() for i in range(5)] == expected
    assert all(window.table.horizontalHeaderItem(i).toolTip() for i in range(5))
    assert window.width() >= window.minimumWidth()
    assert window.height() >= window.minimumHeight()

    window.close()
