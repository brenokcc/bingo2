import os
import mercadopago
from datetime import datetime
from django.core.cache import cache
from django.conf import settings


class MercadoPago():
    def __init__(self):
        self.token = os.environ.get('TOKEN_MERCADO_PAGO')

    def realizar_cobranca_pix(self, nome, cpf, descricao, valor, email):
        data = {
            "transaction_amount": 1.0 if settings.MOCK else float(valor),
            "description": descricao,
            "payment_method_id": "pix",
            "payer": {
                "email": email,
                "first_name": nome.split()[0],
                "last_name": nome.split()[-1],
                "identification": {
                    "type": "CPF",
                    "number": cpf
                }
            }
        }
        if settings.MOCK:
            data = dict(
                identifier='24767778610',
                qrcode='00020126330014br.gov.bcb.pix0111+843272389852040000530398654041.005802BR5908BRENOKCC6010Parnamirim62240520mpqrinter2476777861063043628',
                url='https://www.mercadopago.com.br/payments/24767778610/ticket?caller_id=195280535&hash=e75ff5b0-c1a6-4522-8017-a39633ef6af0',
                status='pending'
            )

            return data
        else:
            sdk = mercadopago.SDK(self.token)
            api = sdk.payment()
            response = api.create(data)
            status = response["status"]
            identifier = response["response"]["id"]
            qrcode = response["response"]['point_of_interaction']['transaction_data']['qr_code']
            url = response["response"]['point_of_interaction']['transaction_data']['ticket_url']
            data = dict(status=status, identifier=identifier, qrcode=qrcode, url=url)
            return data

    def consultar_pagamento_pix(self, identificador):
        if settings.MOCK:
            return 'approved'
        else:
            sdk = mercadopago.SDK(self.token)
            api = sdk.payment()
            status = api.get(identificador)['response']['status']
            return status