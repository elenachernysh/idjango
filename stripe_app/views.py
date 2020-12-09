import json
import stripe
from functools import wraps
from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from iDjango.settings import STRIPE_BEARER
from utils.common_functions import format_date, get_schema
from auth_app.views import AccountsMixin

stripe.api_key = STRIPE_BEARER


def get_info_from_request(decorated):
    @wraps(decorated)
    def wrapper(api, request, *args, **kwargs):
        access_token = request.session.get('access_token')
        invoice_id = request.session.get('invoice_id')
        account_id = request.session.get('account_id')
        if not all((access_token, invoice_id, account_id)):
            return render(request, 'stripe_app/error.html')
        return decorated(api, request, *args, **kwargs)
    return wrapper


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(View):
    """ stripe.error.InvalidRequestError: Invalid URL: URL must be publicly accessible. """

    def get(self, request):
        # TODO not localhost link
        try:
            stripe.WebhookEndpoint.create(
                url='http://localhost:8000/payment/insert-link/',
                enabled_events=[
                    'invoice.created',
                ],
            )
            return HttpResponse(status=200)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(status=400)


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
        return HttpResponse(status=200)


class InvoiceMixin:
    """  Class for handling invoice's views """
    _fields_to_represent_invoice = (
        'period_end', 'customer_name', 'status', 'number', 'subtotal', 'total', 'invoice_pdf', 'created', 'paid'
    )
    _fields_to_represent_line_invoice = (
        'quantity', 'description', 'unit_amount'
    )

    @staticmethod
    def get_invoice(invoice_id: str) -> dict:
        invoice_details = stripe.Invoice.retrieve(invoice_id)
        return invoice_details

    def search(self, line) -> dict:
        result = {}
        for item in line.items():
            if isinstance(item[1], dict):
                result.update(self.search(item[1]))
            elif item[0] in self._fields_to_represent_line_invoice:
                result.update({item[0]: item[1]})
        return result

    def create_context_from_invoice(self, invoice_id: str) -> dict:
        try:
            invoice_details = self.get_invoice(invoice_id)
            result = {
                invoice_key: invoice_details.get(invoice_key)
                for invoice_key in self._fields_to_represent_invoice
            }
            if result.get('created') > datetime.timestamp(datetime.now()):
                return {'error': 'invoice link is expired'}
            # result = dict(filter(lambda elem: elem[0] in self._fields_to_represent_invoice, invoice_details.items()))
            lines = invoice_details.get('lines', {}).get('data', [])
            result.update({'products': [self.search(line=line) for line in lines]})
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            # TODO beautiful error
            return {'error': ''}


class InvoiceView(View, InvoiceMixin):
    """ Detail view of invoice (all info is getting from Stripe by API) """

    def get(self, request, *args, **kwargs):
        invoice_id = kwargs.get("id")
        request.session['invoice_id'] = invoice_id
        context = self.create_context_from_invoice(
            invoice_id=invoice_id
        )
        print(context)
        if 'error' in context:
            return render(request, 'stripe_app/error.html')
        return render(request, 'stripe_app/invoice_detail.html', context)


class ProofPaymentView(View, InvoiceMixin, AccountsMixin):
    """ Page with invoice and selected account views """

    @get_info_from_request
    def post(self, request):
        selected_account_id = request.POST.get('account')
        access_token = request.session.get('access_token')
        invoice_id = request.session.get('invoice_id')
        request.session['account_id'] = selected_account_id
        invoice = self.create_context_from_invoice(
            invoice_id=invoice_id
        )
        accounts = self.get_accounts(
            access_token=access_token,
            account_id=selected_account_id
        )
        if 'error' in invoice or 'error' in accounts:
            return render(request, 'stripe_app/error.html')
        context = {**invoice, **accounts}
        return render(request, 'stripe_app/proof_payment.html', context)


class AuthorizePaymentView(View, AccountsMixin):
    """ Payment! """

    @get_info_from_request
    def get(self, request):
        access_token = request.session.get('access_token')
        invoice_id = request.session.get('invoice_id')
        account_id = request.session.get('account_id')
        bank_account_token = self.create_bank_account_token(access_token=access_token, account_id=account_id)
        if 'error' in bank_account_token:
            return render(request, 'stripe_app/error.html')
        invoice_details = stripe.Invoice.retrieve(invoice_id)
        customer_id = invoice_details.get('customer')
        customer = stripe.Customer.modify(
            customer_id,
            source=bank_account_token.get('stripe_bank_account_token'),
        )
        payment = stripe.Invoice.pay(invoice_id, source=customer.get('default_source'))
        return render(request, 'stripe_app/result_payment.html')
