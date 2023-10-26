from api import endpoints
from api.components import Boxes
from .models import Evento, Cartela, CompraOnline
from .mercadopago import MercadoPago
from . import tasks


class AcessoRapido(endpoints.Endpoint):
    def get(self):
        boxes = Boxes(title='Acesso Rápido')
        if self.check_roles('adm'):
            boxes.append(icon='dollar', label='Meios de Pagamento', url='/api/v1/meiopagamento/')
        boxes.append(icon='users', label='Pessoas', url='/api/v1/pessoa/')
        boxes.append(icon='calendar', label='Eventos', url='/api/v1/evento/')
        boxes.append(icon='cart-plus', label='Compras Online', url='/api/v1/compraonline/')
        return boxes

    def check_permission(self):
        return self.user.is_authenticated


class RealizarCompraOnline(endpoints.Endpoint):
    nome = endpoints.CharField(label='Nome')
    cpf = endpoints.CharField(label='CPF')
    email = endpoints.CharField(label='E-mail')
    telefone = endpoints.CharField(label='Telefone', required=False)
    numero_cartelas = endpoints.IntegerField(label='Número de Cartelas')

    class Meta:
        title = 'Realizar Compra Online'
        icon = 'cart-plus'
        help_text = 'Após o envio do formulário, você será redirecionado para o site do Mercado Pago, onde poderá efetuar o pagamento com total segurança. Após concluir o pagamento, aguarde alguns segundos para que o sistema redirecione você para o sistema novamente.'

    def post(self):
        compra = CompraOnline.objects.create(
            cpf=self.getdata('cpf'), nome=self.getdata('nome'), telefone=self.getdata('telefone'),
            email=self.getdata('email'), numero_cartelas = self.getdata('numero_cartelas')
        )
        self.redirect(compra.url)


    def check_permission(self):
        return True


class VisualizarCompraOnline(endpoints.Endpoint):

    class Meta:
        icon = 'search'
        title = 'Visualizar Compra Online'

    def get(self):
        compra = CompraOnline.objects.getdata(uuid=self.request.GET.getdata('uuid'))
        autoreload = None if compra.is_confirmada() else 30
        return compra.valueset(
            'cpf', 'nome', 'data_hora', 'valor', 'get_status_atual', 'get_cartelas',
            autoreload=autoreload
        )

    def check_permission(self):
        return True


class ConsultarCompraOnline(endpoints.Endpoint):
    cpf = endpoints.CharField(label='CPF')

    class Meta:
        icon = 'search'
        title = 'Consultar Compra Online'

    def get(self):
        return self.objects('bingo.compraonline').filter(cpf=self.getdata('cpf')).fields(
            'cpf', 'nome', 'data_hora', 'valor', 'get_numeros_cartelas', 'get_status'
        )

    def check_permission(self):
        return True


class Dashboard(endpoints.EndpointSet):
    endpoints = AcessoRapido,

    def check_permission(self):
        return self.user.is_authenticated


class Index(endpoints.EndpointSet):
    endpoints = ConsultarCompraOnline, RealizarCompraOnline

    def check_permission(self):
        return True


class GerarCartelas(endpoints.Endpoint):

    class Meta:
        target = 'instance'

    def post(self):
        self.execute(tasks.GerarCartelas(self.instance))
        self.notify('Cartelas geradas com sucesso')

    def check_permission(self):
        return self.check_roles('adm') and not self.instance.talao_set.exists()


class Distribuir(endpoints.Endpoint):

    aplicar_talao = endpoints.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

    class Meta:
        title = 'Distribuir'
        modal = True
        style = 'secondary'
        model = Cartela
        fields = 'responsavel', 'aplicar_talao'
        help_text = 'Informe a pessoa que ficará responsável pela cartela.'

    def post(self):
        self.instance.talao.cartela_set.update(
            responsavel=self.instance.responsavel
        ) if self.getdata('aplicar_talao') else super().submit()

    def check_permission(self):
        return self.instance.responsavel is None and self.check_roles('adm', 'op')


class DevolverCartela(endpoints.Endpoint):
    aplicar_talao = endpoints.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

    class Meta:
        title = 'Devolver'
        modal = True
        style = 'danger'
        fields = 'aplicar_talao',

    def post(self):
        self.instance.responsavel=None
        self.instance.posse = None
        self.instance.realizou_pagamento = None
        self.instance.meio_pagamento = None
        self.instance.comissao = 0
        self.instance.save()
        self.instance.talao.cartela_set.update(
            responsavel=None, posse=None, realizou_pagamento=None, meio_pagamento=None, comissao=0
        ) if self.getdata('aplicar_talao') else super().submit()

    def check_permission(self):
        return self.instance.responsavel and self.instance.realizou_pagamento is None and self.check_roles('adm', 'op')


class InformarPosseCartela(endpoints.Endpoint):
    aplicar_talao = endpoints.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

    class Meta:
        title = 'Repassar'
        modal = True
        style = 'secondary'
        model = Cartela
        fields = 'posse', 'aplicar_talao'

    def post(self):
        self.instance.talao.cartela_set.update(
            posse=self.instance.posse
        ) if self.getdata('aplicar_talao') else super().submit()

    def check_permission(self):
        return self.instance.responsavel and self.instance.realizou_pagamento is None and self.check_roles('adm', 'op')


class PrestarConta(endpoints.Endpoint):
    aplicar_talao = endpoints.BooleanField(label='Aplicar em todo o talão?', initial=False, required=False)

    class Meta:
        title = 'Prestar Contas'
        modal = True
        style = 'success'
        model = Cartela
        fields = 'realizou_pagamento', 'meio_pagamento', 'comissao', 'aplicar_talao',

    def post(self):
        if not self.getdata('realizou_pagamento'):
            self.instance.meio_pagamento = None
            self.instance.comissao = 0
        self.instance.talao.cartela_set.update(
            realizou_pagamento=self.instance.realizou_pagamento,
            meio_pagamento=self.instance.meio_pagamento,
            comissao=self.instance.comissao
        ) if self.getdata('aplicar_talao') else super().submit()

    def on_realizou_pagamento_change(self, realizou_pagamento=None, **kwargs):
        self.enable('comissao', 'meio_pagamento') if realizou_pagamento else self.disable('comissao', 'meio_pagamento')

    def validate_comissao(self, comissao):
        if self.getdata('realizou_pagamento') is None:
            return 0
        if self.getdata('realizou_pagamento'):
            if self.getdata('comissao') is None:
                raise endpoints.ValidationError('Informe a comissão')
            if self.getdata('comissao') > self.instance.talao.evento.valor_comissao_cartela:
                raise endpoints.ValidationError('Valor não pode ser superior a {}'.format(self.instance.talao.evento.valor_comissao_cartela))
            return self.getdata('comissao')
        return 0

    def check_permission(self):
        return self.instance.responsavel and self.check_roles('adm', 'op')


class ExportarCartelasExcel(endpoints.Endpoint):
    class Meta:
        title = 'Exportar para Excel'
        modal = True
        style = 'primary'
        target = 'queryset'

    def post(self):
        rows = []
        valor = None
        rows.append(('Nº da Cartela', 'Talão', 'Responsável', 'Posse', 'Valor da Cartela', 'Valor da Comissão', 'Situação'))
        for obj in self.instance.order_by('numero'):
            if valor is None:
                valor = obj.talao.evento.get_valor_liquido_cartela()
            rows.append((obj.numero, obj.talao.numero, obj.responsavel.nome if obj.responsavel else '', obj.posse.nome if obj.posse else '', valor, obj.comissao or '0', obj.get_situacao()['label']))
        return self.to_csv_file(rows)

    def check_permission(self):
        return True


class AtualizarSituacao(endpoints.Endpoint):

    class Meta:
        icon = 'redo'
        title = 'Atualizar Situação'

    def post(self):
        self.instance.atualizar_situacao()

    def check_permission(self):
        return not self.instance.is_confirmada()


class EfetuarPagamentoOnline(endpoints.Endpoint):

    class Meta:
        icon = 'file-invoice-dollar'
        title = 'Efetuar Pagamento'
        help_text = 'Você será redirecionado para o site do Mercado Pago.'

    def post(self):
        self.redirect(self.instance.url)

    def check_permission(self):
        return not self.instance.is_confirmada()
