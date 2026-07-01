# -*- coding: utf-8 -*-
"""Export du dashboard en PDF."""
# ── RECONSTRUIT ──


def export_dashboard_pdf(html_content, output_path="dashboard_kpi.pdf"):
    """Génère un PDF à partir du HTML du dashboard."""
    try:
        import weasyprint
        weasyprint.HTML(string=html_content).write_pdf(output_path)
        return output_path
    except ImportError:
        try:
            from pdfkit import from_string as pdf_from_string
            pdf_from_string(html_content, output_path)
            return output_path
        except ImportError:
            return None
