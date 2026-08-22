"""Generate printable PDF invoices for completed QuickCart orders."""

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def invoice_filename(order_id: str) -> str:
    return f"QuickCart-Invoice-{order_id}.pdf"


def build_invoice_pdf(order: dict[str, Any]) -> bytes:
    """Create a readable, printable invoice PDF for one saved order."""
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"QuickCart invoice {order['order_id']}",
        author="QuickCart",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="QuickCartTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#0C831F"),
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvoiceMuted",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#64748B"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvoiceTotal",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            alignment=TA_RIGHT,
        )
    )

    created_at = order["created_at"].replace("T", " ").replace("+00:00", " UTC")
    story = [
        Paragraph("QuickCart", styles["QuickCartTitle"]),
        Paragraph("Order invoice - demo checkout", styles["InvoiceMuted"]),
        Spacer(1, 5 * mm),
    ]

    order_details = Table(
        [
            [
                Paragraph("<b>Invoice details</b>", styles["Normal"]),
                Paragraph("<b>Delivery address</b>", styles["Normal"]),
            ],
            [
                Paragraph(
                    f"Order ID: <b>{order['order_id']}</b><br/>"
                    f"Order date: {created_at}<br/>"
                    f"Status: {order['status']}<br/>"
                    f"Payment: {order['payment_method']}",
                    styles["Normal"],
                ),
                Paragraph(
                    f"{order['customer_name']}<br/>"
                    f"{order['address']}<br/>"
                    f"{order['city']} - {order['pincode']}<br/>"
                    f"Phone: {order['phone']}",
                    styles["Normal"],
                ),
            ],
        ],
        colWidths=[84 * mm, 84 * mm],
    )
    order_details.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0FDF4")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBF7D0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DCFCE7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([order_details, Spacer(1, 7 * mm)])

    item_rows = [
        [
            Paragraph("<b>Item</b>", styles["Normal"]),
            Paragraph("<b>Qty</b>", styles["Normal"]),
            Paragraph("<b>Price</b>", styles["Normal"]),
            Paragraph("<b>Line total</b>", styles["Normal"]),
        ]
    ]
    for item in order["items"]:
        item_rows.append(
            [
                Paragraph(item["name"], styles["Normal"]),
                str(item["quantity"]),
                f"Rs. {item['price']:.2f}",
                f"Rs. {item['line_total']:.2f}",
            ]
        )

    items_table = Table(item_rows, colWidths=[85 * mm, 20 * mm, 35 * mm, 38 * mm], repeatRows=1)
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C831F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([items_table, Spacer(1, 4 * mm)])

    totals = Table(
        [
            ["Subtotal", f"Rs. {order['subtotal']:.2f}"],
            [
                "Delivery fee",
                "FREE" if not order["delivery_fee"] else f"Rs. {order['delivery_fee']:.2f}",
            ],
            [
                Paragraph("<b>Total</b>", styles["InvoiceTotal"]),
                Paragraph(f"<b>Rs. {order['total']:.2f}</b>", styles["InvoiceTotal"]),
            ],
        ],
        colWidths=[130 * mm, 48 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 0.75, colors.HexColor("#0C831F")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F0FDF4")),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            totals,
            Spacer(1, 10 * mm),
            Paragraph(
                "Thank you for shopping with QuickCart. This is a demo invoice; no real payment has been processed.",
                styles["InvoiceMuted"],
            ),
        ]
    )

    document.build(story)
    return stream.getvalue()
