DEFAULT_INVOICE_HEADER = r'''<table class="company-header"><tr>
  <td class="company-logo">{% if company.logo_url %}<img src="{{ company.logo_url }}" alt="Company logo">{% endif %}</td>
  <td><div class="company-name">{{ company.legal_name }}</div>{{ company.address|linebreaksbr }}<br>GSTIN: {{ company.gstin }}{% if company.state_code %}<br>State Code: {{ company.state_code }}{% endif %}</td>
  <td class="company-contact"><strong>Name: {{ company.contact_person }}</strong><br>Phone: {{ company.phone }}<br>Email: {{ company.email }}<br>Website: {{ company.website }}<br>PAN: {{ company.pan }}</td>
</tr></table>'''

DEFAULT_INVOICE_TEMPLATE = r'''<style>
* { box-sizing:border-box; }
body { margin:0; color:#111; font:9pt Arial, sans-serif; }
table { width:100%; border-collapse:collapse; table-layout:fixed; }
th,td { border:1px solid #1570ef; padding:4px; vertical-align:top; overflow-wrap:anywhere; }
.company-header td { border:0; padding:2px; }
.company-logo { width:29%; }
.company-logo img { max-width:100%; max-height:22mm; object-fit:contain; }
.company-name { font-size:13pt; font-weight:bold; }
.company-contact { text-align:right; font-size:8pt; }
.invoice-title { margin:5px 0; background:#eef5ff; font-weight:bold; text-align:center; }
.invoice-title td { padding:5px; }
.party-grid { margin-bottom:5px; }
.party-grid th,.invoice-meta th { background:#eef5ff; }
.invoice-meta { margin-bottom:5px; }
.items { font-size:7.5pt; }
.items thead { display:table-header-group; }
.items tr { break-inside:avoid; page-break-inside:avoid; }
.items th { background:#e8f1ff; text-align:center; }
.num { text-align:right; white-space:nowrap; }
.center { text-align:center; }
.invoice-closing { margin-top:5px; break-inside:avoid; page-break-inside:avoid; }
.totals { width:57%; margin-left:auto; }
.totals th { text-align:left; background:#f6f9ff; }
.invoice-footer-layout { width:100%; border-collapse:collapse; table-layout:fixed; }
.invoice-footer-layout>tbody>tr>td { padding:0; vertical-align:top; }
.invoice-footer-layout .totals { width:100%; margin:0; }
.invoice-footer-left { width:60%; }
.invoice-footer-right { width:40%; }
.invoice-footer-inner { width:100%; border-collapse:collapse; table-layout:fixed; }
.invoice-footer-inner th { text-align:center; background:#eef5ff; }
.invoice-footer-bank { width:100%; border-collapse:collapse; table-layout:fixed; }
.invoice-footer-bank td { border:0; }
.invoice-footer-bank-qr { width:32%; text-align:center; vertical-align:middle; }
.invoice-footer-sign { height:22mm; }
.grand-total { background:#fff5a8; font-weight:bold; }
.words { font-weight:bold; text-transform:uppercase; }
.bank-terms { margin-top:5px; }
.bank-terms th { background:#eef5ff; text-align:center; }
.sign-row { height:22mm; }
.small { font-size:7pt; }
</style>
<table class="invoice-title"><tr><td>GSTIN: {{ company.gstin }}</td><td colspan="2">{{ invoice.invoice_type|upper }}</td><td class="small">ORIGINAL FOR RECIPIENT</td></tr></table>
<table class="party-grid"><tr><th colspan="2">Details of Buyer / Billed To</th><th colspan="2">Details of Consignee / Shipped To</th><th colspan="2">Invoice Details</th></tr>
<tr><td>Name</td><td>{{ buyer.name }}</td><td>Name</td><td>{{ buyer.name }}</td><td>Invoice No.</td><td>{{ invoice.invoice_number|default:"DRAFT" }}</td></tr>
<tr><td>Address</td><td>{{ buyer.address|linebreaksbr }}</td><td>Address</td><td>{{ buyer.consignee_address|default:buyer.address|linebreaksbr }}</td><td>Invoice Date</td><td>{{ invoice.invoice_date|date:"d-M-Y" }}</td></tr>
<tr><td>Phone</td><td>{{ buyer.telephone }}</td><td>Phone</td><td>{{ buyer.telephone }}</td><td>Due Date</td><td>{{ invoice.due_date|date:"d-M-Y"|default:"—" }}</td></tr>
<tr><td>GSTIN</td><td>{{ buyer.gstin }}</td><td>GSTIN</td><td>{{ buyer.gstin }}</td><td>Challan No. / Date</td><td>{{ invoice.challan_number }} / {{ invoice.challan_date|date:"d-M-Y"|default:"—" }}</td></tr>
<tr><td>PAN</td><td>{{ buyer.pan }}</td><td>State</td><td>{{ buyer.state_name }} ({{ buyer.state_code }})</td><td>P.O. No. / Date</td><td>{{ invoice.po_number }} / {{ invoice.po_date|date:"d-M-Y"|default:"—" }}</td></tr>
<tr><td>State</td><td>{{ buyer.state_name }} ({{ buyer.state_code }})</td><td>Place of Supply</td><td>{{ buyer.state_name }}</td><td>L.R. / E-Way No.</td><td>{{ invoice.lr_number }} / {{ invoice.eway_number }}</td></tr>
<tr><td>Contact</td><td>{{ buyer.contact_person }}</td><td>Email</td><td>{{ buyer.email }}</td><td>Delivery / Payment</td><td>{{ invoice.delivery_mode }} / {{ invoice.get_payment_type_display }}</td></tr>
</table>
<table class="items"><thead><tr><th rowspan="2" style="width:3%">Sr.</th><th rowspan="2" style="width:18%">Name of Product / Service</th><th rowspan="2" style="width:6%">HSN/SAC</th><th rowspan="2" style="width:6%">Qty</th><th rowspan="2" style="width:7%">Batch No.</th><th rowspan="2" style="width:7%">Rate</th><th rowspan="2" style="width:8%">Taxable Value</th><th colspan="2" style="width:12%">CGST</th><th colspan="2" style="width:12%">SGST</th><th colspan="2" style="width:12%">IGST</th><th rowspan="2" style="width:9%">Total</th></tr><tr><th style="width:4%">%</th><th style="width:8%">Amount</th><th style="width:4%">%</th><th style="width:8%">Amount</th><th style="width:4%">%</th><th style="width:8%">Amount</th></tr></thead><tbody>
{% for line in lines %}<tr><td class="center">{{ forloop.counter }}</td><td>{{ line.description }}{% if line.item_note %}<br><span class="small">{{ line.item_note|linebreaksbr }}</span>{% endif %}</td><td>{{ line.hsn_sac }}</td><td class="num">{{ line.quantity|floatformat:3 }} {{ line.uom }}</td><td>{{ line.batch_number }}</td><td class="num">{{ line.rate|floatformat:2 }}</td><td class="num">{{ line.taxable_value|floatformat:2 }}</td><td class="num">{{ line.cgst_rate|default_if_none:"0.00"|floatformat:2 }}</td><td class="num">{{ line.cgst_amount|floatformat:2 }}</td><td class="num">{{ line.sgst_rate|default_if_none:"0.00"|floatformat:2 }}</td><td class="num">{{ line.sgst_amount|floatformat:2 }}</td><td class="num">{{ line.igst_rate|default_if_none:"0.00"|floatformat:2 }}</td><td class="num">{{ line.igst_amount|floatformat:2 }}</td><td class="num">{{ line.total|floatformat:2 }}</td></tr>{% empty %}<tr><td colspan="14" class="center">No invoice items.</td></tr>{% endfor %}
<tr><th colspan="6" class="num">Total</th><th class="num">{{ invoice.taxable_total|floatformat:2 }}</th><th></th><th class="num">{{ invoice.cgst_total|floatformat:2 }}</th><th></th><th class="num">{{ invoice.sgst_total|floatformat:2 }}</th><th></th><th class="num">{{ invoice.igst_total|floatformat:2 }}</th><th class="num">{{ invoice.items_total|floatformat:2 }}</th></tr>
</tbody></table>
<div class="invoice-closing"><table class="invoice-footer-layout"><tbody><tr>
<td class="invoice-footer-left"><table class="invoice-footer-inner">
<tr><th>Total in words</th></tr><tr><td class="words">{{ total_words }}</td></tr>
<tr><th>Bank Details</th></tr>
<tr><td><table class="invoice-footer-bank"><tr><td>{% for bank in bank_details %}<strong>{{ bank.name }}</strong><br>Account Name: {{ bank.account_name }}<br>Account No.: {{ bank.account_number }}<br>IFSC: {{ bank.ifsc }}<br>Branch: {{ bank.branch }}<br>UPI ID: {{ bank.upi_id }}{% if not forloop.last %}<hr>{% endif %}{% empty %}Bank details not provided.{% endfor %}</td><td class="invoice-footer-bank-qr">{% if qr_data %}<img src="{{ qr_data }}" alt="Payment QR" style="width:25mm;height:25mm"><br>Pay using UPI{% endif %}</td></tr></table></td></tr>
<tr><th>{{ invoice.terms_title|default:"Terms and Conditions" }}</th></tr>
<tr><td>{{ invoice.terms_detail|default:company.terms|linebreaksbr }}{% if invoice.document_remarks %}<br><br>{{ invoice.document_remarks|linebreaksbr }}{% endif %}</td></tr>
<tr><td>Customer Signature</td></tr>
</table></td>
<td class="invoice-footer-right"><table class="totals">
<tr><th>Taxable Amount</th><td class="num">{{ invoice.taxable_total|floatformat:2 }}</td></tr>
{% if invoice.additional_charges %}<tr><th>Additional Charges</th><td class="num">{{ invoice.additional_charges|floatformat:2 }}</td></tr>{% endif %}
{% if invoice.cgst_total %}<tr><th>Add : CGST</th><td class="num">{{ invoice.cgst_total|floatformat:2 }}</td></tr>{% endif %}
{% if invoice.sgst_total %}<tr><th>Add : SGST</th><td class="num">{{ invoice.sgst_total|floatformat:2 }}</td></tr>{% endif %}
{% if invoice.igst_total %}<tr><th>Add : IGST</th><td class="num">{{ invoice.igst_total|floatformat:2 }}</td></tr>{% endif %}
{% if invoice.discount_total %}<tr><th>Discount{% if invoice.discount_mode == "percent" %} ({{ invoice.discount_amount }}%){% endif %}</th><td class="num">{% if invoice.discount_is_addition %}+{% else %}−{% endif %} {{ invoice.discount_total|floatformat:2 }}</td></tr>{% endif %}
{% if invoice.tcs_amount %}<tr><th>TCS{% if invoice.tcs_mode == "percent" %} ({{ invoice.tcs_rate }}%){% endif %}</th><td class="num">{% if invoice.tcs_is_deduction %}−{% else %}+{% endif %} {{ invoice.tcs_amount|floatformat:2 }}</td></tr>{% endif %}
{% if invoice.round_off_enabled %}<tr><th>Round Off</th><td class="num">{{ invoice.round_off_amount|floatformat:2 }}</td></tr>{% endif %}
<tr><th>Total Tax</th><td class="num">{{ invoice.tax_total|floatformat:2 }}</td></tr><tr class="grand-total"><th>Total Amount After Tax</th><td class="num">₹ {{ invoice.grand_total|floatformat:2 }}</td></tr>
<tr><td colspan="2" class="num">(E &amp; O.E.)</td></tr><tr><td colspan="2" class="small center">Certified that the particulars given above are true and correct.</td></tr>
<tr><td colspan="2" class="center"><strong>For {{ company.legal_name }}</strong><div class="invoice-footer-sign"></div><strong>Authorised Signatory</strong></td></tr>
</table></td>
</tr></tbody></table></div>
'''
