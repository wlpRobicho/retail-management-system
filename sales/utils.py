import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from django.core.files.base import ContentFile
from .models import SalesTransaction

def generate_receipt_pdf(transaction: SalesTransaction):
    # Create an in-memory buffer to store the PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)  # Initialize the PDF canvas with A4 page size
    width, height = A4  # Get the width and height of the page
    y = height - 30  # Start drawing from the top of the page

    # Header section
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, y, "🧾 ALJAMAA STORE RECEIPT")  # Centered receipt title
    y -= 40

    # Transaction metadata (e.g., ID, date, cashier, payment method)
    p.setFont("Helvetica", 11)
    p.drawString(30, y, f"Transaction #: {transaction.id}")
    y -= 20
    p.drawString(30, y, f"Date: {transaction.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 20
    p.drawString(30, y, f"Cashier: {transaction.cashier.name}")
    y -= 20
    p.drawString(30, y, f"Payment: {transaction.payment_method.capitalize()}")
    if transaction.payment_method == "cash":
        y -= 20
        p.drawString(30, y, f"Amount Received: DA {transaction.amount_received}")
        y -= 20
        p.drawString(30, y, f"Change Due: DA {transaction.change_due}")
    if transaction.discount_code:
        y -= 20
        p.drawString(30, y, f"Discount Code: {transaction.discount_code.code} (10%)")

    # Separator line
    y -= 30
    p.line(30, y, width - 30, y)
    y -= 20

    # Item headers
    p.setFont("Helvetica-Bold", 11)
    p.drawString(30, y, "Item")  # Column for item name
    p.drawString(200, y, "Qty x Unit")  # Column for quantity and unit price
    p.drawString(400, y, "Total")  # Column for total price
    y -= 15
    p.line(30, y, width - 30, y)  # Line under headers
    y -= 20
    p.setFont("Helvetica", 10)

    # Loop through all items in the transaction and display them
    for item in transaction.items.all():
        line_total = item.quantity * item.unit_price  # Calculate total for the line
        p.drawString(30, y, f"{item.product.name}")  # Product name
        p.drawString(200, y, f"{item.quantity} x {item.unit_price} DA")  # Quantity and unit price
        p.drawString(400, y, f"{line_total:.2f} DA")  # Total price for the item
        y -= 15

        # Display discount information if applicable
        if transaction.discount_code:
            discount = item.product.selling_price - item.unit_price
            if discount > 0:
                p.setFont("Helvetica-Oblique", 8)
                p.drawString(200, y, f"Discount: -{discount:.2f} DA")
                y -= 12
                p.setFont("Helvetica", 10)

        # Start a new page if the current page is full
        if y < 100:
            p.showPage()
            y = height - 30

    # Final totals section
    y -= 20
    p.line(30, y, width - 30, y)  # Line above totals
    y -= 30
    p.setFont("Helvetica-Bold", 12)
    p.drawString(30, y, f"Total Amount: DA {transaction.total_amount}")  # Display total amount
    y -= 20

    # Refund notice if the transaction is a refund
    if transaction.is_refund:
        p.setFont("Helvetica-Bold", 12)
        p.setFillColorRGB(1, 0, 0)  # Set text color to red
        p.drawString(30, y, "Refund Transaction")  # Display refund notice
        p.setFillColorRGB(0, 0, 0)  # Reset text color to black
        y -= 20

    # Footer section
    p.setFont("Helvetica-Oblique", 9)
    p.drawString(30, y, "Thank you for shopping with us!")  # Thank-you message
    y -= 10
    p.drawString(30, y, "ALJAMAA Store • Algeria")  # Store details

    # Finalize the PDF and save it to the buffer
    p.showPage()
    p.save()

    # Save the PDF to the database as a file
    filename = f"receipt_{transaction.id}.pdf"
    transaction.receipt.save(filename, ContentFile(buffer.getvalue()))
    transaction.save()

    # Return the buffer for further use (e.g., downloading)
    return buffer
