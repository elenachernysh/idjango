import json
import plaid
from django.shortcuts import render
from django.views import View
from django.http import JsonResponse, HttpResponse
from utils.common_functions import reduce_info

from iDjango.settings import PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV, PLAID_VERSION, PLAID_COUNTRY_CODES, \
    PLAID_PRODUCTS, PLAID_REDIRECT_URI

client = plaid.Client(client_id=PLAID_CLIENT_ID,
                      secret=PLAID_SECRET,
                      environment=PLAID_ENV,
                      api_version=PLAID_VERSION)


class LinkTokenView(View):
    """ Creates a link_token, which is required as a parameter when initializing Link """

    def post(self, request):
        try:
            response = client.LinkToken.create(
                {
                    'user': {
                        'client_user_id': '123-test-user-id',
                    },
                    'client_name': "Plaid Test App",
                    'products': PLAID_PRODUCTS,
                    'country_codes': PLAID_COUNTRY_CODES,
                    'language': "en",
                    'redirect_uri': PLAID_REDIRECT_URI,
                    'account_filters': {
                        'depository': {
                            'account_subtypes': ['checking', 'savings'],
                        },
                    },
                }
            )
            link_token = response.get('link_token')
            request.session['link_token'] = link_token
            return JsonResponse({'link_token': link_token})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'false', 'message': 'something went wrong'}, status=400)


class AccessTokenView(View):
    """ Exchange a Link public_token and access_token. """

    def post(self, request):
        payload = json.loads(request.body)
        public_token = payload.get('public_token')
        try:
            exchange_response = client.Item.public_token.exchange(public_token)
            access_token = exchange_response.get('access_token')
            request.session['access_token'] = access_token
            return JsonResponse({'access_token': access_token})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(status=400)


def get_accounts(
        access_token: str,
        acceptable_type: str,
        acceptable_subtypes: tuple,
        needed_keys: tuple,
        account_id: str = None
) -> list:
    options = {}
    if account_id:
        options = {'account_ids': [account_id]}
    response = client.Accounts.get(access_token, _options=options)
    raw_accounts = response['accounts']
    print(raw_accounts)
    accounts = reduce_info(
        needed_keys=needed_keys,
        data_to_reduce=[account for account in raw_accounts if account.get('type') == acceptable_type and account.get('subtype') in acceptable_subtypes]
    )
    print(accounts)
    return accounts


class AccountsView(View):
    """ Detail view of bank accounts """
    _acceptable_type = 'depository'
    _acceptable_subtypes = ('checking', 'savings')
    _fields_to_represent = ('account_id', 'name', 'mask')

    def get(self, request, *args, **kwargs):
        access_token = request.session['access_token']
        invoice_id = request.session['invoice_id']
        accounts = get_accounts(
            access_token=access_token,
            acceptable_type=self._acceptable_type,
            acceptable_subtypes=self._acceptable_subtypes,
            needed_keys=self._fields_to_represent
        )
        return render(request, 'auth_app/accounts.html', {
            'accounts': accounts,
            'invoice_id': invoice_id
        })


def create_bank_account_token(access_token: str, account_id: str):
    stripe_response = client.Processor.stripeBankAccountTokenCreate(access_token, account_id)
    print(stripe_response)
    return stripe_response.get('stripe_bank_account_token')

# 2222
# 4444
# There are no valid checking or savings account(s) associated with this Item.



# plaid.errors.InvalidInputError: account_id specified does not belong to a depository account


# [
# {'account_id': 'D3rEEwVJ5Qf3RXKXg9dBcd9kE5Eg3buvqRRJJ', 'balances': {'available': 100, 'current': 110, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '0000', 'name': 'Plaid Checking', 'official_name': 'Plaid Gold Standard 0% Interest Checking', 'subtype': 'checking', 'type': 'depository'},
# {'account_id': 'V8XzzgrB5Kt79wDwz1axcNg5PDPQ3ECWMyyEZ', 'balances': {'available': 200, 'current': 210, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '1111', 'name': 'Plaid Saving', 'official_name': 'Plaid Silver Standard 0.1% Interest Saving', 'subtype': 'savings', 'type': 'depository'},
# {'account_id': 'wBz665JvjrCw4x5x89Rmto8dMwM4E9SrXRRmz', 'balances': {'available': None, 'current': 1000, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '2222', 'name': 'Plaid CD', 'official_name': 'Plaid Bronze Standard 0.2% Interest CD', 'subtype': 'cd', 'type': 'depository'},
# {'account_id': '5ZwXXV6kgqC5KJPJjzVgtrznv3voXMtZryy8y', 'balances': {'available': None, 'current': 410, 'iso_currency_code': 'USD', 'limit': 2000, 'unofficial_currency_code': None}, 'mask': '3333', 'name': 'Plaid Credit Card', 'official_name': 'Plaid Diamond 12.5% APR Interest Credit Card', 'subtype': 'credit card', 'type': 'credit'},
# {'account_id': 'JPGyyb9J5ouEQ898aL6BcRznmvmDw6Cd8MMk6', 'balances': {'available': 43200, 'current': 43200, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '4444', 'name': 'Plaid Money Market', 'official_name': 'Plaid Platinum Standard 1.85% Interest Money Market', 'subtype': 'money market', 'type': 'depository'},
# {'account_id': 'k1eRRmkvqgIw7GqGjBmptkgXWnWe61tW5DDo5', 'balances': {'available': None, 'current': 320.76, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '5555', 'name': 'Plaid IRA', 'official_name': None, 'subtype': 'ira', 'type': 'investment'},
# {'account_id': 'lLXRR1d6K8uQNxKxZ6q7tJeWPQPvGDCZ3ggRV', 'balances': {'available': None, 'current': 23631.9805, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '6666', 'name': 'Plaid 401k', 'official_name': None, 'subtype': '401k', 'type': 'investment'},
# {'account_id': 'qEm66j9vxnF8zXxXlBb6t7Q9D8DmWGidKPPRq', 'balances': {'available': None, 'current': 65262, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '7777', 'name': 'Plaid Student Loan', 'official_name': None, 'subtype': 'student', 'type': 'loan'},
# {'account_id': 'KjeLLVZJ5gfeGvyv9XkWcnNgLRL1deCVXkk1B', 'balances': {'available': None, 'current': 56302.06, 'iso_currency_code': 'USD', 'limit': None, 'unofficial_currency_code': None}, 'mask': '8888', 'name': 'Plaid Mortgage', 'official_name': None, 'subtype': 'mortgage', 'type': 'loan'}
# ]