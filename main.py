"""FastAPI application implementing an e‑commerce site with eSewa payment and admin panel.

This app uses a SQLite database to store products and orders, and
provides endpoints for clients to browse products, create orders and
initiate payments via eSewa. An admin interface allows adding and
editing products and confirming order payments. HTML templates use
Jinja2 for server‑side rendering.
"""

import os
import base64
import json
import hmac
import hashlib
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional

import database

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount static assets (CSS, JS, images)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Jinja2 templates location
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# eSewa configuration
PORT = int(os.environ.get("PORT", 8000))
BASE_URL = os.environ.get("BASE_URL", f"http://localhost:{PORT}")
ESEWA_PRODUCT_CODE = os.environ.get("ESEWA_PRODUCT_CODE", "EPAYTEST")
ESEWA_SECRET_KEY = os.environ.get("ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")
ESEWA_FORM_URL = os.environ.get(
    "ESEWA_FORM_URL", "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
)


@app.on_event("startup")
def startup() -> None:
    """Initialise the database when the server starts."""
    database.init_db()


def html_response(filename: str) -> FileResponse:
    path = os.path.join(BASE_DIR, "templates", filename)
    return FileResponse(path, media_type="text/html")


@app.get("/")
def index() -> FileResponse:
    return html_response("index.html")


@app.get("/cart.html")
def cart_page() -> FileResponse:
    return html_response("cart.html")


@app.get("/checkout.html")
def checkout_page() -> FileResponse:
    return html_response("checkout.html")


@app.get("/success.html")
def success_page() -> FileResponse:
    return html_response("success.html")


@app.get("/failure.html")
def failure_page() -> FileResponse:
    return html_response("failure.html")


# API endpoints
@app.get("/api/products")
def api_products() -> dict:
    return {"products": database.get_products()}


@app.post("/api/order")
async def api_create_order(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    required = ["customerName", "customerEmail", "customerPhone", "customerAddress", "cart", "tax_amount", "service_charge", "delivery_charge"]
    for field in required:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing field {field}")
    try:
        order = database.create_order(
            customer_name=data["customerName"],
            customer_email=data["customerEmail"],
            customer_phone=data["customerPhone"],
            customer_address=data["customerAddress"],
            cart=data["cart"],
            tax_amount=float(data["tax_amount"]),
            service_charge=float(data["service_charge"]),
            delivery_charge=float(data["delivery_charge"]),
        )
        return JSONResponse({"orderId": order["id"]})
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Server error")


def generate_signature(total_amount: str, transaction_uuid: str) -> str:
    """Generate HMAC SHA256 signature for eSewa form fields."""
    data_string = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={ESEWA_PRODUCT_CODE}"
    digest = hmac.new(ESEWA_SECRET_KEY.encode(), data_string.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


@app.post("/api/initiate-payment")
async def api_initiate_payment(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    order_id = data.get("orderId")
    if not order_id:
        raise HTTPException(status_code=400, detail="Missing orderId")
    order = database.get_order_by_id(int(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    # Generate signature using total_amount (formatted with two decimals) and transaction_uuid
    signature = generate_signature(f"{order['total_amount']:.2f}", order["transaction_uuid"])
    form_data = {
        "amount": f"{order['amount']:.2f}",
        "tax_amount": f"{order['tax_amount']:.2f}",
        "total_amount": f"{order['total_amount']:.2f}",
        "transaction_uuid": order["transaction_uuid"],
        "product_code": ESEWA_PRODUCT_CODE,
        "product_service_charge": f"{order['service_charge']:.2f}",
        "product_delivery_charge": f"{order['delivery_charge']:.2f}",
        "success_url": f"{BASE_URL}/esewa-callback",
        "failure_url": f"{BASE_URL}/esewa-callback?status=fail",
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": signature,
    }
    return JSONResponse({"formData": form_data, "gatewayUrl": ESEWA_FORM_URL})


@app.get("/esewa-callback")
async def esewa_callback(request: Request) -> RedirectResponse:
    # Check for failure status
    fail_status = request.query_params.get("status")
    if fail_status == "fail":
        return RedirectResponse(url="/failure.html")
    encoded_data = request.query_params.get("data")
    if not encoded_data:
        return RedirectResponse(url="/failure.html")
    try:
        decoded_json = base64.b64decode(encoded_data).decode()
        payload = json.loads(decoded_json)
        received_sig = payload.get("signature")
        verify_string = (
            f"transaction_code={payload.get('transaction_code')},"
            f"status={payload.get('status')},"
            f"total_amount={payload.get('total_amount')},"
            f"transaction_uuid={payload.get('transaction_uuid')},"
            f"product_code={ESEWA_PRODUCT_CODE},"
            f"signed_field_names={payload.get('signed_field_names')}"
        )
        computed_sig = base64.b64encode(
            hmac.new(ESEWA_SECRET_KEY.encode(), verify_string.encode(), hashlib.sha256).digest()
        ).decode()
        # Verify signature and status
        if computed_sig == received_sig and payload.get("status") == "COMPLETE":
            # Update order status
            database.update_order_status(payload.get("transaction_uuid"), "COMPLETED")
            return RedirectResponse(url="/success.html")
    except Exception:
        pass
    # On any verification failure
    return RedirectResponse(url="/failure.html")


# Admin pages
@app.get("/admin")
def admin_home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})


@app.get("/admin/products")
def admin_products(
    request: Request,
    edit_id: Optional[int] = None,
    delete_id: Optional[int] = None,
) -> HTMLResponse:
    # Handle deletion if requested
    if delete_id:
        database.delete_product(int(delete_id))
        return RedirectResponse(url="/admin/products", status_code=303)
    products = database.get_products()
    product_to_edit = database.get_product(edit_id) if edit_id else None
    return templates.TemplateResponse(
        "admin_products.html",
        {"request": request, "products": products, "product_to_edit": product_to_edit},
    )


# A GET endpoint to save a product (add or update) via query parameters. Using
# GET avoids the dependency on python-multipart for form data parsing. The
# admin form should submit via GET to `/admin/save-product`.
@app.get("/admin/save-product")
def admin_save_product(
    id: Optional[int] = None,
    name: str = None,
    description: str = None,
    price: float = None,
    image_url: str = None,
) -> RedirectResponse:
    if not all([name, description, price, image_url]):
        # If required fields missing, just redirect back
        return RedirectResponse(url="/admin/products", status_code=303)
    try:
        if id:
            database.update_product(int(id), name, description, float(price), image_url)
        else:
            database.create_product(name, description, float(price), image_url)
    except Exception:
        pass
    return RedirectResponse(url="/admin/products", status_code=303)


@app.get("/admin/orders")
def admin_orders(request: Request) -> HTMLResponse:
    orders = database.get_orders()
    return templates.TemplateResponse(
        "admin_orders.html",
        {"request": request, "orders": orders},
    )


@app.get("/admin/orders/confirm")
def admin_confirm_order(transaction_uuid: str) -> RedirectResponse:
    # Mark order as COMPLETED
    database.update_order_status(transaction_uuid, "COMPLETED")
    return RedirectResponse(url="/admin/orders", status_code=303)