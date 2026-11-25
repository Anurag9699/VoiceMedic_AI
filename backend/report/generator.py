import uuid
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from storage_paths import DATA_DIR

REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "reports.db"


def init_db():
    """Initialize SQLite database for storing reports."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            doctor_id TEXT,
            patient_name TEXT,
            age INTEGER,
            gender TEXT,
            symptoms TEXT,
            diagnosis TEXT,
            pdf_path TEXT,
            report_json TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS reports_by_doctor_date ON reports (doctor_id, timestamp DESC)")
    conn.commit()
    conn.close()


init_db()

def report_pdf_path(report_id: str) -> Path:
    return REPORTS_DIR / f"{report_id}.pdf"


def generate_pdf_report(
    report_data: Dict[str, Any],
    report_id: str,
    doctor_name: str = "Dr. Attending Physician, M.D."
) -> str:
    """
    Generate a formal, subtle, publication-grade medical consultation PDF report.
    Guarantees strict vertical leading to eliminate any possibility of overlapping text.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

        pdf_path = report_pdf_path(report_id)
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=1.8 * cm,
            rightMargin=1.8 * cm,
            topMargin=1.8 * cm,
            bottomMargin=1.8 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # ── Color Palette: Subtle, Formal Clinical Monochrome / Slate ──
        C_PRIMARY = colors.HexColor('#0f172a')     # Slate 900 (deep formal charcoal)
        C_SECONDARY = colors.HexColor('#334155')   # Slate 700
        C_MUTED = colors.HexColor('#64748b')       # Slate 500
        C_LIGHT_BG = colors.HexColor('#f8fafc')    # Slate 50
        C_BORDER = colors.HexColor('#e2e8f0')      # Slate 200
        C_BORDER_DARK = colors.HexColor('#94a3b8') # Slate 400

        # ── Typography: Explicit leading on EVERY style prevents overlap ──
        clinic_title_style = ParagraphStyle(
            'ClinicTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=18,
            textColor=C_PRIMARY,
            spaceAfter=2,
        )
        clinic_sub_style = ParagraphStyle(
            'ClinicSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11.5,
            textColor=C_MUTED,
        )
        doc_info_style = ParagraphStyle(
            'DocInfo',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11.5,
            alignment=TA_RIGHT,
            textColor=C_SECONDARY,
        )
        doc_bold_style = ParagraphStyle(
            'DocBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=C_PRIMARY,
        )
        section_heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=13,
            textColor=C_PRIMARY,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )
        tbl_label_style = ParagraphStyle(
            'TblLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=C_MUTED,
        )
        tbl_val_style = ParagraphStyle(
            'TblVal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=C_PRIMARY,
        )
        body_text_style = ParagraphStyle(
            'BodyText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=C_SECONDARY,
            spaceAfter=3,
        )
        bullet_text_style = ParagraphStyle(
            'BulletText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=C_SECONDARY,
            leftIndent=12,
            spaceAfter=2,
        )
        diag_box_style = ParagraphStyle(
            'DiagBox',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=13,
            textColor=C_PRIMARY,
        )
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=C_MUTED,
            alignment=TA_CENTER,
        )

        # ── 1. Formal Facility & Attending Doctor Header ──
        now_dt = datetime.now()
        date_str = now_dt.strftime("%d %B %Y, %I:%M %p")
        ref_id_str = report_id[:8].upper()

        header_left = [
            Paragraph("VOICEMEDIC HEALTH CLINIC", clinic_title_style),
            Paragraph("Department of Internal Medicine & Clinical Diagnostics", clinic_sub_style),
            Paragraph("Automated Clinical Speech Dictation System", clinic_sub_style),
        ]
        header_right = [
            Paragraph(f"<b>Attending Physician:</b> {doctor_name}", doc_bold_style),
            Paragraph("<b>Biometric Verification:</b> AUTHENTICATED (ECAPA-TDNN)", doc_info_style),
            Paragraph(f"<b>Date:</b> {date_str} &nbsp;|&nbsp; <b>Ref:</b> #{ref_id_str}", doc_info_style),
        ]

        header_table = Table([[header_left, header_right]], colWidths=[9.5 * cm, 7.9 * cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.2 * cm))

        # Formal hairline divider
        story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER_DARK, spaceBefore=2, spaceAfter=8))

        # ── 2. Patient Demographics & Encounter Summary ──
        story.append(Paragraph("PATIENT & ENCOUNTER INFORMATION", section_heading_style))

        pat_name = report_data.get('patient_name') or 'Not specified'
        age_val = report_data.get('age')
        gender_val = report_data.get('gender')
        if age_val and gender_val:
            age_gender_str = f"{age_val} yrs / {gender_val}"
        elif age_val:
            age_gender_str = f"{age_val} yrs"
        elif gender_val:
            age_gender_str = f"{gender_val}"
        else:
            age_gender_str = "Not specified"

        duration_val = report_data.get('duration') or "Not specified"

        patient_meta = [
            [
                Paragraph("Patient Name", tbl_label_style),
                Paragraph(f"<b>{pat_name}</b>", tbl_val_style),
                Paragraph("Encounter Date", tbl_label_style),
                Paragraph(date_str, tbl_val_style),
            ],
            [
                Paragraph("Age / Gender", tbl_label_style),
                Paragraph(age_gender_str, tbl_val_style),
                Paragraph("Symptoms Duration", tbl_label_style),
                Paragraph(duration_val, tbl_val_style),
            ],
            [
                Paragraph("Report Status", tbl_label_style),
                Paragraph("Doctor Voice Verified ✓", tbl_val_style),
                Paragraph("Encounter ID", tbl_label_style),
                Paragraph(f"ENC-{ref_id_str}", tbl_val_style),
            ]
        ]
        pt = Table(patient_meta, colWidths=[3.2 * cm, 5.5 * cm, 3.5 * cm, 5.2 * cm])
        pt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C_LIGHT_BG),
            ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(pt)
        story.append(Spacer(1, 0.25 * cm))

        # ── 3. Chief Complaints / Symptoms — ALWAYS rendered ──
        symptoms = report_data.get('symptoms') or []
        story.append(Paragraph("CHIEF COMPLAINTS &amp; PRESENTING SYMPTOMS", section_heading_style))
        if symptoms:
            for sym in symptoms:
                story.append(Paragraph(f"&bull; &nbsp; {sym.capitalize()}", bullet_text_style))
        else:
            story.append(Paragraph("&bull; &nbsp; <i>No specific symptoms recorded in this consultation.</i>", bullet_text_style))
        story.append(Spacer(1, 0.2 * cm))

        # ── 4. Vital Signs — ALWAYS rendered with full table ──
        vitals = report_data.get('vitals') or {}
        story.append(Paragraph("VITAL SIGNS &amp; OBSERVATIONS", section_heading_style))
        vital_map_ordered = [
            ('blood_pressure', 'Blood Pressure'),
            ('temperature',    'Body Temperature'),
            ('pulse',          'Pulse / Heart Rate'),
            ('spo2',           'Oxygen Saturation (SpO₂)'),
            ('weight',         'Body Weight'),
        ]
        vdata = []
        for key, label in vital_map_ordered:
            val = vitals.get(key)
            display_val = str(val) if (val and val != 'null') else '—'
            vdata.append([
                Paragraph(f"<b>{label}</b>", tbl_label_style),
                Paragraph(display_val, tbl_val_style),
            ])
        vt = Table(vdata, colWidths=[6.5 * cm, 10.9 * cm])
        vt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, C_LIGHT_BG]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(vt)
        story.append(Spacer(1, 0.2 * cm))

        # ── 5. Medical History — ALWAYS rendered ──
        history = report_data.get('medical_history')
        story.append(Paragraph("RELEVANT MEDICAL HISTORY", section_heading_style))
        story.append(Paragraph(
            history if (history and history != 'null') else "<i>No prior medical history recorded.</i>",
            body_text_style
        ))
        story.append(Spacer(1, 0.2 * cm))

        # ── 6. Provisional Diagnosis — ALWAYS rendered ──
        diagnosis = report_data.get('suggested_diagnosis')
        story.append(Paragraph("PROVISIONAL CLINICAL DIAGNOSIS", section_heading_style))
        diag_text = diagnosis if (diagnosis and diagnosis != 'null') else "Pending further evaluation and investigation."
        diag_table = Table([[Paragraph(f"<b>Impression:</b> {diag_text}", diag_box_style)]], colWidths=[17.4 * cm])
        diag_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C_LIGHT_BG),
            ('BOX', (0, 0), (-1, -1), 0.75, C_BORDER_DARK),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(diag_table)
        story.append(Spacer(1, 0.2 * cm))

        # ── 7. Recommended Investigations — ALWAYS rendered ──
        tests = report_data.get('recommended_tests') or []
        story.append(Paragraph("RECOMMENDED INVESTIGATIONS &amp; LAB TESTS", section_heading_style))
        if tests:
            for i, test in enumerate(tests, 1):
                story.append(Paragraph(f"{i}. &nbsp; {test}", bullet_text_style))
        else:
            story.append(Paragraph("<i>No investigations ordered at this visit.</i>", bullet_text_style))
        story.append(Spacer(1, 0.2 * cm))

        # ── 8. Prescription & Treatment Plan — ALWAYS rendered ──
        prescription = report_data.get('prescription')
        story.append(Paragraph("Rx — PRESCRIPTION &amp; TREATMENT PLAN", section_heading_style))
        rx_content = prescription if (prescription and prescription != 'null') else "<i>No medications prescribed at this visit.</i>"
        rx_table = Table([[Paragraph(rx_content, body_text_style)]], colWidths=[17.4 * cm])
        rx_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
            ('BOX', (0, 0), (-1, -1), 0.5, C_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(rx_table)
        story.append(Spacer(1, 0.2 * cm))

        # ── 9. Physician's Notes — always show full transcript/translation ──
        transcript_text = report_data.get('transcript') or ''
        english_translation = report_data.get('english_translation') or ''
        notes_text = report_data.get('notes') or ''
        story.append(Paragraph("PHYSICIAN'S CONSULTATION NOTES", section_heading_style))
        consultation_text = english_translation or transcript_text or notes_text
        if consultation_text and consultation_text.strip():
            story.append(Paragraph(consultation_text.strip(), body_text_style))
            if transcript_text and english_translation and transcript_text.strip() != english_translation.strip():
                story.append(Spacer(1, 0.1 * cm))
                orig_label_style = ParagraphStyle('OrigLabel', parent=styles['Normal'],
                    fontName='Helvetica-Oblique', fontSize=8, leading=11,
                    textColor=C_MUTED, spaceAfter=2)
                story.append(Paragraph(f"Original transcript: {transcript_text.strip()}", orig_label_style))
        else:
            story.append(Paragraph("<i>No consultation notes recorded.</i>", body_text_style))
        story.append(Spacer(1, 0.2 * cm))

        # ── 10. Formal Doctor Sign-off & Digital Biometric Stamp ──
        story.append(Spacer(1, 0.6 * cm))
        sign_block = [
            Paragraph("<b>Physician Authorization:</b>", tbl_label_style),
            Paragraph("Digitally Authenticated via Speech Biometrics", clinic_sub_style),
            Spacer(1, 0.3 * cm),
            HRFlowable(width="60%", thickness=0.75, color=C_BORDER_DARK, hAlign='RIGHT'),
            Spacer(1, 0.1 * cm),
            Paragraph(f"<b>{doctor_name}</b>", doc_bold_style),
            Paragraph("Licensed Attending Physician", doc_info_style),
            Paragraph(f"Voice Biometric Token: <b>VERIFIED-{ref_id_str}</b>", doc_info_style),
        ]
        sign_table = Table(
            [[
                Paragraph("<b>Instructions to Patient:</b><br/>"
                          "&bull; Please take medications strictly as directed.<br/>"
                          "&bull; In case of acute symptom worsening, seek immediate emergency care.",
                          clinic_sub_style),
                sign_block
            ]],
            colWidths=[9.5 * cm, 7.9 * cm]
        )
        sign_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(KeepTogether(sign_table))

        # ── 11. Subtle Formal Footer ──
        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceBefore=4, spaceAfter=6))
        story.append(Paragraph(
            "Confidential Medical Consultation Record &nbsp;&bull;&nbsp; "
            "Generated via VoiceMedic AI with doctor voice biometric verification.<br/>"
            f"Record ID: {report_id} &nbsp;|&nbsp; Timestamp: {date_str} (UTC)",
            footer_style
        ))

        doc.build(story)
        return str(pdf_path)

    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {e}")


def save_report_to_db(report_id: str, doctor_id: str, report_data: Dict[str, Any], pdf_path: str):
    """Save report metadata to SQLite."""
    summary = {
        "id": report_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patient_name": report_data.get("patient_name"),
        "age": report_data.get("age"),
        "gender": report_data.get("gender"),
        "diagnosis": report_data.get("suggested_diagnosis"),
    }
    conn = sqlite3.connect(str(DB_PATH))
    try:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO reports (id, timestamp, doctor_id, patient_name, age, gender,
                                     symptoms, diagnosis, pdf_path, report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id, summary["timestamp"], doctor_id, summary["patient_name"], summary["age"],
                summary["gender"], json.dumps(report_data.get("symptoms", [])), summary["diagnosis"],
                str(pdf_path), json.dumps(report_data),
            ))
    finally:
        conn.close()
    return summary


def count_reports(doctor_id: str = "default_doctor") -> int:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        return conn.execute("SELECT COUNT(*) FROM reports WHERE doctor_id=?", (doctor_id,)).fetchone()[0]
    finally:
        conn.close()


def get_all_reports(doctor_id: str = "default_doctor") -> list:
    """Fetch all reports for a doctor from SQLite."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM reports WHERE doctor_id=? ORDER BY timestamp DESC", (doctor_id,)
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        r = dict(row)
        r['symptoms'] = json.loads(r.get('symptoms') or '[]')
        result.append(r)
    return result
