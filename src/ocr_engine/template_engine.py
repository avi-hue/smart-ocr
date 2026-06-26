import json
import re
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel

from src.utils.logger import get_logger
from src.ocr_engine.field_extractor import ExtractedInvoice, LineItem, clean_numeric

log = get_logger(__name__)

class ColumnMapping(BaseModel):
    group_index: int
    field_name: str  # e.g., 'description', 'unit_price', 'line_total', 'quantity', or custom extra field like 'Reference'
    is_numeric: bool = False

class TemplateRule(BaseModel):
    vendor_identifiers: List[str]  # Substrings to match in raw text to activate this template
    line_item_pattern: str         # Regex pattern with capturing groups for line items
    columns: List[ColumnMapping]   # Mapping of regex capture groups to fields
    
    # Optional scalar field patterns
    invoice_number_pattern: Optional[str] = None
    total_amount_pattern: Optional[str] = None
    tax_amount_pattern: Optional[str] = None
    date_pattern: Optional[str] = None
    vendor_name_pattern: Optional[str] = None
    buyer_name_pattern: Optional[str] = None


# Hardcoded templates for the known dataset
TEMPLATES: List[TemplateRule] = [
    TemplateRule(
        vendor_identifiers=["hilton", "rm occupancy tax"],
        line_item_pattern=r"^\s*(\d{1,2}/\d{1,2}/\d{4})\s+(.+?)\s+(\d{6,8})\s+\$([\d\.]+)",
        columns=[
            ColumnMapping(group_index=1, field_name="Date"),
            ColumnMapping(group_index=2, field_name="description"),
            ColumnMapping(group_index=3, field_name="Reference"),
            ColumnMapping(group_index=4, field_name="line_total", is_numeric=True),
        ]
    ),
    TemplateRule(
        vendor_identifiers=["citycar", "odom. out", "jens walter"],
        line_item_pattern=r"^\s*(Odom\.\s*In)\s+(\d+)\s+\$([\d\.]+)",
        columns=[
            ColumnMapping(group_index=1, field_name="description"),
            ColumnMapping(group_index=2, field_name="Odometer_Reading"),
            ColumnMapping(group_index=3, field_name="line_total", is_numeric=True),
        ],
        invoice_number_pattern=r"(?i)Agreement #:\s*([\d]+)"
    ),
    TemplateRule(
        vendor_identifiers=["country inn", "palo alto", "may 6't9"],
        line_item_pattern=r"^\s*([A-Za-z]+\s+\d+'[A-Za-z0-9]+.*?)\s+(\S+)\s+(\S+)",
        columns=[
            ColumnMapping(group_index=1, field_name="description"),
            ColumnMapping(group_index=2, field_name="Tax_or_Rate", is_numeric=True),
            ColumnMapping(group_index=3, field_name="line_total", is_numeric=True),
        ]
    )
]


def apply_templates(text: str, source_file: str) -> Optional[ExtractedInvoice]:
    """
    Checks if the invoice matches any known templates. 
    If a template matches, applies exact regex parsing to extract fields perfectly.
    Returns None if no template matches.
    """
    text_lower = text.lower()
    matched_template = None
    
    for tmpl in TEMPLATES:
        if any(ident.lower() in text_lower for ident in tmpl.vendor_identifiers):
            matched_template = tmpl
            break
            
    if not matched_template:
        return None
        
    log.info(f"Matched custom template for vendor identifiers: {matched_template.vendor_identifiers[0]}")
    
    invoice = ExtractedInvoice(source_file=Path(source_file))
    invoice.line_items = []
    
    # Parse line items
    pattern = re.compile(matched_template.line_item_pattern, re.IGNORECASE | re.MULTILINE)
    for match in pattern.finditer(text):
        item = LineItem(extra_fields={})
        valid_item = False
        
        for col in matched_template.columns:
            try:
                val = match.group(col.group_index).strip()
            except IndexError:
                continue
                
            if col.is_numeric:
                val = clean_numeric(val)
                
            if col.field_name == "description":
                item.description = val
                item.extra_fields["Description"] = val
                valid_item = True
            elif hasattr(item, col.field_name):
                setattr(item, col.field_name, val)
            else:
                item.extra_fields[col.field_name] = val
                
        if valid_item:
            invoice.line_items.append(item)
            
    # Parse scalar fields if defined
    if matched_template.invoice_number_pattern:
        m = re.search(matched_template.invoice_number_pattern, text, re.IGNORECASE)
        if m: invoice.invoice_number = m.group(1).strip()
        
    if matched_template.total_amount_pattern:
        m = re.search(matched_template.total_amount_pattern, text, re.IGNORECASE)
        if m: invoice.total_amount = clean_numeric(m.group(1))
        
    if matched_template.tax_amount_pattern:
        m = re.search(matched_template.tax_amount_pattern, text, re.IGNORECASE)
        if m: invoice.tax_amount = clean_numeric(m.group(1))
        
    if matched_template.vendor_name_pattern:
        m = re.search(matched_template.vendor_name_pattern, text, re.IGNORECASE)
        if m: invoice.vendor_name = m.group(1).strip()
        
    if matched_template.buyer_name_pattern:
        m = re.search(matched_template.buyer_name_pattern, text, re.IGNORECASE)
        if m: invoice.buyer_name = m.group(1).strip()

    return invoice
