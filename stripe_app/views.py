import json
from abc import ABC

import stripe
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from iDjango.settings import STRIPE_BEARER
from utils.common_functions import format_date, get_schema
from auth_app.views import get_accounts, create_bank_account_token

stripe.api_key = STRIPE_BEARER


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(View):
    """ stripe.error.InvalidRequestError: Invalid URL: URL must be publicly accessible.
        Consider using a tool like the Stripe CLI to test webhooks locally: https://github.com/stripe/stripe-cli
    """

    def get(self, request):
        stripe.WebhookEndpoint.create(
            url='http://localhost:8000/payment/insert-link/',
            enabled_events=[
                'invoice.created',
            ],
        )
        return HttpResponse(status=200)


@method_decorator(csrf_exempt, name='dispatch')
class InsertLinkView(View):
    """ Insert link to invoice into field memo (description) """

    def post(self, request):
        raw_payload = request.body
        payload = json.loads(raw_payload)
        try:
            event = stripe.Event.construct_from(
                payload, stripe.api_key
            )
            invoice_id = payload.get("data", {}).get("object", {}).get("id")
        except ValueError as e:
            return HttpResponse(status=400)
        print(event.type)
        if event.type == 'invoice.created':
            schema = get_schema(request.is_secure())
            invoice_redirect_url = f'{schema}{request.get_host()}/user/invoice/{invoice_id}'
            invoice = stripe.Invoice.modify(
                invoice_id,
                description=f'Please follow link for ACH Direct Debit payment {invoice_redirect_url}',
            )
            print(invoice)
        return HttpResponse(status=200)


class InvoiceMixin:
    """ Abstract class for invoices """
    _fields_to_represent_invoice = (
        'period_end', 'customer_name', 'status', 'status_transitions', 'number', 'subtotal', 'total', 'invoice_pdf'
    )
    _fields_to_represent_line_invoice = (
        'quantity', 'description', 'unit_amount'
    )

    def dk(self, line) -> dict:
        result = {}
        for item in line.items():
            if isinstance(item[1], dict):
                result.update(self.dk(item[1]))
            elif item[0] in self._fields_to_represent_line_invoice:
                result.update({item[0]: item[1]})
        return result

    def create_context_from_invoice(self, invoice_id: str) -> dict:
        invoice_details = stripe.Invoice.retrieve(invoice_id)
        result = {invoice_key: invoice_details.get(invoice_key) for invoice_key in self._fields_to_represent_invoice}
        # result = dict(filter(lambda elem: elem[0] in self._fields_to_represent_invoice, invoice_details.items()))
        lines = invoice_details.get('lines', {}).get('data', [])
        result.update({'products': [self.dk(line=line) for line in lines]})
        return result


class InvoiceView(View, InvoiceMixin):
    """ Detail view of invoice (all info is getting from Stripe by API) """

    def get(self, request, *args, **kwargs):
        invoice_id = kwargs.get("id")
        request.session['invoice_id'] = invoice_id
        if not invoice_id:
            return HttpResponse(status=400)
        context = self.create_context_from_invoice(
            invoice_id=invoice_id
        )
        return render(request, 'stripe_app/invoice_detail.html', context)


class ProofPaymentView(View, InvoiceMixin):
    """ Page with invoice and selected account views """
    _acceptable_type = 'depository'
    _acceptable_subtypes = ('checking', 'savings')
    _fields_to_represent = ('account_id', 'name', 'mask')

    def post(self, request, *args, **kwargs):
        selected_account_id = request.POST.get('account')
        access_token = request.session.get('access_token')
        invoice_id = request.session.get('invoice_id')
        if not all((selected_account_id, access_token, invoice_id)):
            return HttpResponse(status=400)
        request.session['account_id'] = selected_account_id
        context = self.create_context_from_invoice(
            invoice_id=invoice_id
        )
        accounts = get_accounts(
            access_token=access_token,
            acceptable_subtypes=self._acceptable_subtypes,
            acceptable_type=self._acceptable_type,
            needed_keys=self._fields_to_represent,
            account_id=selected_account_id
        )
        context.update({'accounts': accounts})
        return render(request, 'stripe_app/proof_payment.html', context)


class AuthorizePaymentView(View):

    def get(self, request):
        access_token = request.session.get('access_token')
        invoice_id = request.session.get('invoice_id')
        account_id = request.session.get('account_id')
        bank_account_token = create_bank_account_token(access_token=access_token, account_id=account_id)
        customer_id = "cus_IU8vl97l8utQXH"
        customer_update = stripe.Customer.modify(
            customer_id,
            source=bank_account_token,
        )
        customer = stripe.Customer.retrieve(customer_id)
        print(customer)
        payment = stripe.Invoice.pay(invoice_id, source=customer.get('default_source'))
        return render(request, 'stripe_app/result_payment.html')

# There are no valid checking or savings account(s) associated with this Item.