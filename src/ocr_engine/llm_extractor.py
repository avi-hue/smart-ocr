"""
llm_extractor.py - Use Google Gemini to semantically extract invoice fields from raw text.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field

from google import genai
from google.genai import types

from src.utils.logger import get_logger
from src.ocr_engine.field_extractor import ExtractedInvoice, LineItem

log = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Schema for Strict LLM Output
# ──────────────────────────────────────────────────────────────────────────────

class LLMLineItem(BaseModel):
    sr_no: Optional[str] = Field(None, description="Serial number or item index")
    description: Optional[str] = Field(None, description="Name or description of the product/service")
    hsn_sac_code: Optional[str] = Field(None, description="HSN or SAC code for the item")
    quantity: Optional[str] = Field(None, description="Quantity of items purchased")
    unit_price: Optional[str] = Field(None, description="Price per unit of the item")
    discount: Optional[str] = Field(None, description="Discount amount or percentage applied to the item")
    tax_rate: Optional[str] = Field(None, description="Tax rate percentage (e.g. 18%) applied to the item")
    tax_amount: Optional[str] = Field(None, description="Total tax amount for the item")
    cgst_rate: Optional[str] = Field(None, description="CGST tax rate if split")
    cgst_amount: Optional[str] = Field(None, description="CGST tax amount if split")
    sgst_rate: Optional[str] = Field(None, description="SGST tax rate if split")
    sgst_amount: Optional[str] = Field(None, description="SGST tax amount if split")
    line_total: Optional[str] = Field(None, description="Total line amount after price * qty + tax")

class LLMInvoiceData(BaseModel):
    invoice_number: Optional[str] = Field(None, description="Unique identifier for the invoice")
    invoice_date: Optional[str] = Field(None, description="Date the invoice was issued")
    due_date: Optional[str] = Field(None, description="Date payment is due")
    purchase_order: Optional[str] = Field(None, description="PO Number or Order Number")
    vendor_name: Optional[str] = Field(None, description="Name of the selling company / vendor")
    vendor_address: Optional[str] = Field(None, description="Address of the selling company")
    vendor_gstin: Optional[str] = Field(None, description="GSTIN or Tax ID of the vendor")
    vendor_pan: Optional[str] = Field(None, description="PAN number of the vendor")
    buyer_name: Optional[str] = Field(None, description="Name of the customer or buyer (To / Ship To)")
    buyer_address: Optional[str] = Field(None, description="Address of the customer")
    subtotal: Optional[str] = Field(None, description="Subtotal amount before tax")
    tax_amount: Optional[str] = Field(None, description="Total tax amount for the invoice")
    total_amount: Optional[str] = Field(None, description="Grand total payable amount")
    currency: Optional[str] = Field(None, description="Currency symbol or code (e.g. USD, EUR, INR)")
    line_items: List[LLMLineItem] = Field(default_factory=list, description="List of all purchased items")


# ──────────────────────────────────────────────────────────────────────────────
# Extraction Logic
# ──────────────────────────────────────────────────────────────────────────────

# Characters per token is roughly 4 for English text.
# Capping at ~4 000 tokens keeps each request well within free-tier limits.
_MAX_CHARS = 128_000


def extract_invoice_via_llm(text: str, source_file: str | Path) -> ExtractedInvoice:
    """
    Pass raw invoice text to Gemini and return structured ExtractedInvoice.

    The input text is truncated to _MAX_CHARS characters before sending to the
    API to reduce token consumption and avoid hitting rate limits.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in a .env file or terminal.")

    # Truncate text to reduce token usage per request
    if len(text) > _MAX_CHARS:
        log.warning(
            "Invoice text is {} chars — truncating to {} to stay within token limits.",
            len(text), _MAX_CHARS,
        )
        text = text[:_MAX_CHARS]

    log.info("Sending invoice '{}' to Gemini for semantic extraction...", Path(source_file).name)

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert OCR invoice parser. Your task is to semantically extract all relevant invoice fields from the following raw text.
    The text may be messy, unstructured, or lack clear labels.
    - Carefully identify the Vendor (who is selling/billing) and the Buyer (who is buying/paying/shipping to).
    - If the Vendor Name is not explicitly labeled, infer it from the company name at the top or bottom of the document.
    - CRITICAL: You MUST extract all billed products, services, or fees into the `line_items` array.
    
    Raw Invoice Text:
    ====================
    {text}
    ====================
    """

    import time
    import re

    # Exponential backoff delays (seconds) for 429 rate-limit retries
    # Attempt:  1    2    3     4     5
    # Wait(s):  15   30   60   120   240
    BACKOFF_BASE = 15
    MAX_RETRIES = 5

    data: LLMInvoiceData | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LLMInvoiceData,
                    temperature=0.0,
                ),
            )

            # Pydantic automatically parses the JSON response into our model
            data = LLMInvoiceData.model_validate_json(response.text)
            break  # Success — exit retry loop

        except Exception as e:
            error_msg = str(e)
            is_retryable_overload = "503" in error_msg or "10054" in error_msg or "Connection" in error_msg
            is_rate_limited = "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg

            if is_rate_limited:
                if attempt < MAX_RETRIES - 1:
                    # Prefer the API-suggested retry delay; fall back to exponential backoff
                    delay_match = re.search(r'retry[_ ]after[":\s]*(\d+)', error_msg, re.IGNORECASE)
                    api_suggested = int(delay_match.group(1)) if delay_match else None
                    wait = api_suggested if api_suggested else BACKOFF_BASE * (2 ** attempt)
                    log.warning(
                        "Gemini rate limit hit (429). Waiting {}s before retry {}/{}...",
                        wait, attempt + 1, MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
            elif is_retryable_overload and attempt < MAX_RETRIES - 1:
                wait = 5 * (attempt + 1)  # 5s, 10s, 15s …
                log.warning(
                    "Gemini API overloaded (503). Retrying {}/{} in {}s...",
                    attempt + 1, MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue

            log.error("LLM Extraction failed after {} attempt(s): {}", attempt + 1, e)
            return ExtractedInvoice(source_file=Path(source_file))

    if data is None:
        log.error("LLM Extraction exhausted all {} retries.", MAX_RETRIES)
        return ExtractedInvoice(source_file=Path(source_file))

    # Map Pydantic model back to our existing dataclass system
    invoice = ExtractedInvoice(
        source_file=Path(source_file),
        invoice_number=data.invoice_number,
        invoice_date=data.invoice_date,
        due_date=data.due_date,
        purchase_order=data.purchase_order,
        vendor_name=data.vendor_name,
        vendor_address=data.vendor_address,
        vendor_gstin=data.vendor_gstin,
        vendor_pan=data.vendor_pan,
        buyer_name=data.buyer_name,
        buyer_address=data.buyer_address,
        subtotal=data.subtotal,
        tax_amount=data.tax_amount,
        total_amount=data.total_amount,
        currency=data.currency,
    )

    for li in data.line_items:
        item = LineItem(
            sr_no=li.sr_no,
            description=li.description,
            hsn_sac_code=li.hsn_sac_code,
            quantity=li.quantity,
            unit_price=li.unit_price,
            discount=li.discount,
            tax_rate=li.tax_rate,
            tax_amount=li.tax_amount,
            cgst_rate=li.cgst_rate,
            cgst_amount=li.cgst_amount,
            sgst_rate=li.sgst_rate,
            sgst_amount=li.sgst_amount,
            line_total=li.line_total,
        )
        invoice.line_items.append(item)

    # Assume high confidence since the LLM extracted it semantically
    invoice.extraction_confidence = {k: 1.0 for k in data.model_dump().keys() if getattr(data, k)}
    
    log.info("LLM Extraction successful. Found {} line items.", len(invoice.line_items))
    return invoice
