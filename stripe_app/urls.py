from django.urls import path
from .views import WebhookView, InsertLinkView, InvoiceView, ProofPaymentView, AuthorizePaymentView


app_name = "stripe_app"

urlpatterns = [
    path('webhook/', WebhookView.as_view(), name='webhook'),
    path('insert-link/', InsertLinkView.as_view(), name='insert_link'),
    path('invoice/<str:id>/', InvoiceView.as_view(), name='invoice'),
    path('proof-payment/', ProofPaymentView.as_view(), name='proof_payment'),
    path('payment/', AuthorizePaymentView.as_view(), name='payment'),
]
