import os
import mercadopago
from datetime import datetime
from django.core.cache import cache
from django.conf import settings


class MercadoPago():
    def __init__(self):
        self.mock = False
        self.token = os.environ.get('TOKEN_MERCADO_PAGO')

    def realizar_cobranca_pix(self, nome, cpf, descricao, valor, email):
        data = {
            "transaction_amount": 1.0 if self.mock else float(valor),
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
        if self.mock:
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

    def consultar_pagamento_pix(self, identificador, data_hora):
        if self.mock:
            return 'approved' if datetime.now().minute > data_hora.minute else 'pending'
        else:
            sdk = mercadopago.SDK(self.token)
            api = sdk.payment()
            status = api.get(identificador)['response']['status']
            return status

    def consultar_pagamento(self, referencia, data_hora):
        if self.mock:
            return 'approved' if datetime.now().minute > data_hora.minute else 'pending'
        else:
            sdk = mercadopago.SDK(self.token)
            api = sdk.payment()
            filters = dict(sort='date_created', criteria='desc', external_reference=referencia, range='date_created', begin_date='NOW-2DAYS', end_date='NOW')
            dados = api.search(filters=filters)
            for resultado in dados['response']['results']:
                return resultado['status']

    def realizar_checkout_pro(self, nome, cpf, descricao, valor, email, ref, callback):
        if self.mock:
            return dict(ref=ref, url='https://mercadopago.com.br')
        preference_data = {
            "items": [
                {
                    "title": nome,
                    "currency_id": "BRL",
                    "description": descricao,
                    "quantity": 1,
                    "unit_price": float(valor)
                }
            ],
            "payer": {
                "name": nome,
                "email": email,
                "identification": {
                    "type": "CPF",
                    "number": cpf.replace('.', '').replace('-', '')
                }
            },
            "back_urls": {
                "success": callback,
                "failure": callback,
                "pending": callback
            },
            "auto_return": "approved",
            "statement_descriptor": "Pagamento Online",
            "external_reference": ref,
        }

        sdk = mercadopago.SDK(self.token)
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]
        return dict(ref=ref, url=preference['init_point'])
